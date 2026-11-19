# TTRSS 维护版

基于 [HenryQW/Awesome-TTRSS](https://github.com/HenryQW/Awesome-TTRSS)，保留其提交历史、插件/主题集成与 MIT 许可；实际应用来自 [tt-rss/tt-rss](https://github.com/tt-rss/tt-rss)，适用应用及插件各自许可证。上游 README 已保存在 `docs/README.upstream.md`。这不是上游官方镜像。

## 本仓库维护范围

- 跟踪容器上游与 TT-RSS 应用更新，`upstream-lock.json` 记录审阅的应用/容器提交。
- 集成 `src/bridge.php`：FlareSolverr RSS bridge，密钥只通过 `/etc/ttrss-bridge.key` 挂载；保留旧 `?key=` 用法，推荐 `X-Bridge-Key` 请求头，避免密钥进入 URL 日志。
- 加入 1/3/5/10 分钟订阅刷新选项，默认将失效更新锁等待从 10 分钟减为 1 分钟。**不会批量修改用户已有订阅频率，不承诺所有文章一分钟内更新**，实际还受上游站点、并发及更新进程影响。
- 维护 nginx 安全基线，当前要求 1.30.7；CI 验证 PHP、配置、刷新补丁和未鉴权 bridge 拒绝访问。
- GitHub Actions 发布 `ghcr.io/jiemo9527/ttrss:<commit前7位>` 和 `latest`，支持 amd64/arm64。生产固定 SHA 标签；不要仅因定时构建成功自动部署。

## 配置

```yaml
environment:
  TTRSS_FAST_REFRESH: "true"
  TTRSS_UPDATE_LOCK_MINUTES: "1"  # 1..10
volumes:
  - ./secrets/bridge.key:/etc/ttrss-bridge.key:ro
```

设 `TTRSS_FAST_REFRESH=false`，在新建容器时保留上游刷新默认值。Bridge 默认固定连接同网络 `http://flaresolverr:8191/v1`。密钥缺失/错误返回 403，上游失败返回 502，不输出原始上游内容或凭据。

**安全边界**：bridge 仅供受信任用户；FlareSolverr 可访问其网络并跟随跳转，密钥鉴权不等于 SSRF 隔离。限制 FlareSolverr 网络权限，不要将它直接暴露公网。`bridge.key`、数据库、真实 `.env`、生产 compose 不入库。部署时保留数据库和自有挂载，尤其不能删除原有 bridge key。

## 更新流程

1. `git fetch upstream`，审阅 `upstream/main` 的变化；合并时保留 maintenance 文件和 workflow。
2. `python scripts/check-upstream.py` 检查应用/容器来源；有更新时先审阅再同时调整 `upstream-lock.json` 与 Dockerfile 中 `TTRSS_REF`。
3. 插件/主题仍沿用上游的移动分支下载方式，**尚未逐个锁定提交**；定时构建可能改变这些内容，部署前必须测试，不将它称为完全可复现构建。
4. 安全更新不能只比较应用 SHA：系统包/插件也可能更新。本仓库每周构建，保持 nginx 版本检查；未来安全基线上调时修改 Dockerfile 与 smoke test。
5. 发布后对候选镜像做独立数据库测试；备份数据库后在维护窗口切换，仅替换应用容器，不升级 PostgreSQL 主版本。

## 测试

```sh
php tests/maintenance.php
TEST_IMAGE=ghcr.io/jiemo9527/ttrss:<sha7> sh tests/maintenance-smoke.sh
python scripts/check-upstream.py
```

## 与现有部署迁移

此仓库已内置 bridge 和快速刷新补丁，迁移后不要继续挂旧 `ttrss-entrypoint.sh` 覆盖入口；`bridge.php` 只读挂载也可在确认兼容后移除。**本仓库初次建立不自动迁移线上服务**，避免将应用更新/数据库 schema 更新与 nginx 安全修复混为一个不可回退操作。
