# TTRSS 维护版

基于 [HenryQW/Awesome-TTRSS](https://github.com/HenryQW/Awesome-TTRSS)，保留其提交历史、插件/主题集成与 MIT 许可；实际应用来自 [tt-rss/tt-rss](https://github.com/tt-rss/tt-rss)，适用应用及插件各自许可证。上游 README 已保存在 `docs/README.upstream.md`。这不是上游官方镜像。

## 本仓库维护范围

- **自动同步上游**：每小时检查 Awesome-TTRSS 与 TT-RSS 应用；有更新时自动导入、全量测试（回归 + 镜像构建 + 订阅抓取 e2e），通过后快进 `main` 并发布镜像。`upstream-lock.json` 记录当前同步到的提交。
- 集成 `src/bridge.php`：FlareSolverr RSS bridge，密钥只通过 `/etc/ttrss-bridge.key` 挂载；保留旧 `?key=` 用法，推荐 `X-Bridge-Key` 请求头，避免密钥进入 URL 日志。
- **对 TT-RSS 源码的修改放在 `patches/`**，构建时打进镜像（不是容器启动时注入）：
  - 订阅更新间隔增加 **1/3/5/10 分钟**选项；
  - 中断的更新多久后可重试改为可配置 `UPDATE_LOCK_MINUTES`（1–10，镜像默认 1，上游固定 10）；
  - **订阅源可以用任意端口**（上游只允许 80/443）；内网地址只放行 `ALLOW_PORTS` 中的端口，本机回环和链路本地地址（含云厂商元数据 169.254.169.254）始终拒绝。
  - `http://` 订阅上游本来就支持，无需修改。
  - 不会批量修改已有订阅的更新频率。
- 维护 nginx 安全基线（`scripts/check-nginx-version.sh`：1.30.7+ 稳定版或 1.31.9+），构建和冒烟测试都会校验，低于基线直接失败。
- **自带主题 `enterprise` / `enterprise_night` / `enterprise_auto`**（`themes/enterprise/`）：构建时用固定版本 TT-RSS 的 LESS 源码编译并放进 `themes.local/`，只是新增可选项，不改默认值和现有用户的选择。TT-RSS 升级后如果主题对应的上游结构变了，构建会直接失败，不会悄悄发出样式错乱的镜像。切换与回退方法见 [themes/enterprise/README.md](themes/enterprise/README.md)。
- GitHub Actions 发布 `ghcr.io/jiemo9527/ttrss:<sha7>`、`<sha7>-<日期>` 和 `latest`，支持 amd64/arm64。每天重建一次，拉入 Alpine 的安全更新（nginx、PHP、OpenSSL 等）。生产建议固定带日期的标签；镜像发布不会自动部署到服务器。

## 配置

```yaml
environment:
  UPDATE_LOCK_MINUTES: "1"        # 1..10，中断的更新多少分钟后重试
  ALLOW_PORTS: "80,443,8877"      # 内网订阅源允许的端口；公网源任意端口都可以
  TTRSS_DAEMON_SLEEP_INTERVAL: "60"
volumes:
  - ./secrets/bridge.key:/etc/ttrss-bridge.key:ro
```

旧变量 `TTRSS_UPDATE_LOCK_MINUTES` 仍兼容；`TTRSS_FAST_REFRESH` 已废弃（1/3/5/10 分钟选项现在总是存在，选不选由你）。Bridge 默认固定连接同网络 `http://flaresolverr:8191/v1`。密钥缺失/错误返回 403，上游失败返回 502，不输出原始上游内容或凭据。

**安全边界**：bridge 仅供受信任用户；FlareSolverr 可访问其网络并跟随跳转，密钥鉴权不等于 SSRF 隔离。限制 FlareSolverr 网络权限，不要将它直接暴露公网。`bridge.key`、数据库、真实 `.env`、生产 compose 不入库。部署时保留数据库和自有挂载，尤其不能删除原有 bridge key。

## 更新流程

自动（`.github/workflows/upstream.yml`，每小时第 7 分钟，也可手动触发）：

1. `scripts/sync-upstream.py --apply` 取 Awesome-TTRSS `main` 与 TT-RSS `main` 的最新提交。
2. 容器上游的变更以补丁方式三方合并导入；本仓库自有的 `README.md`、`docker-compose.yml`、`.github/workflows`、`dependabot.yml` 不被覆盖，上游 README / workflows 归档到 `docs/` 供对照。TT-RSS 应用更新只改 `Dockerfile` 的 `TTRSS_REF`。
3. 同步前会在新的 TT-RSS 提交上试打 `patches/*.patch`；打不上就停下。
4. 候选提交推到 `bot/upstream-sync`，跑完整测试；**全部通过才快进 `main`**，随后发布镜像。
5. 冲突、补丁打不上、上游历史改写或测试失败时不改 `main`，自动开一个 “Upstream sync needs attention” issue。

手动处理冲突：

```sh
git fetch upstream
python scripts/sync-upstream.py           # 只检查
python scripts/sync-upstream.py --apply   # 本地生成同步提交，冲突时报告文件
```

解决后提交、推送 `main`；`push` 会触发构建与发布。

### 修改 / 新增 TT-RSS 源码补丁

```sh
git clone https://github.com/tt-rss/tt-rss /tmp/tt && cd /tmp/tt
git checkout <Dockerfile 里的 TTRSS_REF>
git apply /path/to/ttrss/patches/*.patch   # 先套上现有补丁
# 修改代码……
git diff > /path/to/ttrss/patches/0001-update-intervals-and-feed-ports.patch
```

补丁需要对应的测试写进 `tests/patches-test.php`（在构建好的镜像里运行）。

其他说明：

- 插件/主题仍按上游方式下载各自的移动分支，**未逐个锁定提交**，每次构建可能变化；不要把它当作完全可复现构建，部署前先测试。
- 安全基线上调时，修改 `scripts/check-nginx-version.sh`（构建和冒烟测试共用）。
- 生产切换：先用独立数据库验证候选镜像，备份数据库后在维护窗口只替换应用容器，不升级 PostgreSQL 主版本。

## 测试

```sh
python tests/sync-upstream-test.py
TEST_IMAGE=ghcr.io/jiemo9527/ttrss:<tag> sh tests/maintenance-smoke.sh
IMAGE=ghcr.io/jiemo9527/ttrss:<tag> sh tests/e2e.local.sh   # 本机 Docker 跑订阅抓取 e2e
```

## 快速刷新的实际效果

刷新频率由两部分决定：订阅的更新间隔（1/3/5/10 分钟选项），以及更新守护进程的轮询间隔 `TTRSS_DAEMON_SLEEP_INTERVAL`（TT-RSS 默认 **120 秒**）。想让 1 分钟选项真正生效，还需设置 `TTRSS_DAEMON_SLEEP_INTERVAL=60`；订阅数量多时同时关注 `TTRSS_DAEMON_MAX_JOBS`、`TTRSS_DAEMON_FEED_LIMIT`。

## 与现有部署迁移

此仓库已内置 bridge 和源码补丁，迁移后不要继续挂旧 `ttrss-entrypoint.sh` 覆盖入口；`bridge.php` 只读挂载也可在确认兼容后移除。**本仓库初次建立不自动迁移线上服务**，避免将应用更新/数据库 schema 更新与 nginx 安全修复混为一个不可回退操作。
