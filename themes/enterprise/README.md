# Enterprise 主题

现代企业风格的 TT-RSS 主题：中性灰白底、单一深蓝强调色、未读蓝点加粗、正文约 720px 阅读宽度、系统中文字体。
只改样式，不改 TT-RSS 的页面结构，所以上游升级时风险低。

| 主题名（偏好设置 → 主题） | 说明 |
| --- | --- |
| `enterprise` | 浅色 |
| `enterprise_night` | 深色（深灰，不是纯黑） |
| `enterprise_auto` | 跟随系统浅色/深色 |

截图（真实页面，非效果图）见 [docs/design/screenshots/](../../docs/design/screenshots/)；最初的交互效果图在 [docs/design/enterprise-theme-mockup.html](../../docs/design/enterprise-theme-mockup.html)。

## 切换与回退

主题是**每个用户自己选的**，镜像只是多放了几个可选文件，不改默认值，也不改任何人当前的主题。

- **切换**：偏好设置 → 偏好设置 → 主题，选 `enterprise*`，点"保存设置"，页面会自动刷新。
- **回到原来的主题**：同一个下拉框选回原来的（例如 `feedly-sepia-contrast`），或选"默认"回到 TT-RSS 原生界面。
- **界面坏了、进不去设置时**：登录页勾选"安全模式"再登录。本次会话会用 TT-RSS 默认主题（同时临时停用插件），进设置改回主题后正常登出再登录即可。
- **运维侧强制重置**（不需要登录界面）：

  ```sh
  # 把所有用户的主题改回默认；也可以把 '' 换成 'feedly-sepia-contrast.css'
  docker exec <db-container> psql -U <user> -d <db> -c \
    "UPDATE ttrss_user_prefs2 SET value = '' WHERE pref_name = 'USER_CSS_THEME' AND value LIKE 'enterprise%';"
  ```

- **镜像回滚**：回到不含该主题的旧镜像时，若用户仍选着 `enterprise*`，TT-RSS 找不到文件会自动按默认主题渲染，不会报错。

## 构建

`build.mjs` 在镜像构建阶段运行（Dockerfile 的 `themes` stage），使用固定版本 TT-RSS 自带的 LESS 源码，以及该版本 `package-lock.json` 锁定的 `less` 版本：

- `enterprise.less` / `enterprise_night.less` 引入 TT-RSS 的 `light_base.less` / `night_base.less`，再用 `_tokens_*.less` 覆盖变量，最后叠加 `_components.less`。
- TT-RSS 的控件样式（`lib/flat-ttrss`）是预编译 CSS，`build.mjs` 会把其中的上游强调色系整体换成我们的色值，输出到 `themes.local/enterprise/`。
- 上游文件结构变了（找不到要替换的 `@import`、强调色残留、出现新的相对路径、输出过小）时**构建直接失败**，不会悄悄发出坏主题。

本地预览（需要 Node 和一份 TT-RSS 源码）：

```sh
npm install less@<TT-RSS 锁定版本>
node themes/enterprise/build.mjs --ttrss /path/to/tt-rss --out /path/to/tt-rss/themes.local --node-modules .
```

改色只需要改 `tokens.json`（控件）和 `_tokens_light.less` / `_tokens_dark.less`（页面），两处保持一致。

## 已知限制

- "全部 / 未读 / 加星"在 TT-RSS 里是下拉菜单，主题只能改外观，不能改成并排按钮。
- 效果图里正文顶部的阅读进度在 TT-RSS 中不存在，主题没有加。
- 第三方插件自己注入的样式不一定跟随主题配色。
