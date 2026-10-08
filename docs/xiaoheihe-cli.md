# 小黑盒 Skill 与 CLI

小黑盒集成走 `Skill + CLI`，不启动 MCP。Easel 的聊天、技能列表和 `easel skill` 可以发现 `skill-xiaoheihe-publisher`。这是 AI 技能入口，不是 Web 原生账号页或发布页的新平台按钮。

## 使用

Python 3.10+ 可运行仓库自带 CLI，无需全局安装 `xhh-sdk`。真实账号操作使用 Windows DPAPI，在线 App 请求还需要用户提供 Java 17+、签名器和登录凭据。首次配置见[技能设置](../skills/openclaw/skill-xiaoheihe-publisher/references/setup.md)。账号与签名资源不随仓库分发。

在 Easel 根目录运行：

```console
python skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py --version
easel skill xiaoheihe-publisher -i "为指定账号准备小黑盒图文，先展示计划，确认后再发布"
```

Agent 可以调用完整的账号登录、签名器配置、上传和读回命令。受控发帖入口按顺序执行：

```console
python skills/shared/scripts/xiaoheihe_publish.py plan outputs/game-review/assets/post.json --account ALIAS --mode public --out outputs/game-review/assets/xhh-operation
python skills/shared/scripts/xiaoheihe_publish.py show outputs/game-review/assets/xhh-operation
python skills/shared/scripts/xiaoheihe_publish.py submit outputs/game-review/assets/xhh-operation --approval APPROVED_SHA256 --exec
python skills/shared/scripts/xiaoheihe_publish.py reconcile outputs/game-review/assets/xhh-operation
```

先准备 spec 和本地图片，格式见[发布说明](../skills/openclaw/skill-xiaoheihe-publisher/references/publishing.md)。plan/show 不登录、不联网；submit 才验证账号并真实上传、发帖。草稿也是服务端写入。发布前必须由用户确认具体账号、模式、内容和图片。发生未知结果时只核对，不自动重发。

## 版本与来源

- 内置 `xhh-publisher-kit 0.1.0rc1`，原 CLI `0.5.0rc4+standalone.7`。
- 原 CLI 的 25 个 wheel 成员逐字节保留，`vendor/SOURCE.json` 记录完整来源和文件哈希。
- Kit 修正图片提交形态，先上传冻结图片，再把返回 URL 与尺寸写入 HTML 正文，最后调用原 CLI 发帖。
- 快照升级只用 `python scripts/sync_xiaoheihe_kit.py sync`，检查用 `python scripts/sync_xiaoheihe_kit.py check`。不要手改 vendor。
- 上游包采用 MIT，Easel 适配采用本仓库 Apache-2.0；许可证保留在对应目录。

## 本轮验收

2026-10-08 使用测试账号通过 Easel 包装器完成公开模式图文发布。编辑读回确认完整中文、emoji 和图片保留；另一登录账号可以读取同帖。CDN 将图片转为 WebP，尺寸和画面已核对。测试帖子与草稿均删除后确认消失。上传对象无支持的删除接口，可能继续保留。

本轮复用已有 App 会话，并非重新完成短信登录。匿名网页触发 CAPTCHA，未证明未登录访问。自动回执仍为 `acknowledged`，不把有限列表核对伪装成全量验证。

本机 OpenClaw 模型服务返回 HTTP 401，模型自主执行演示未通过；独立 AI 消费者通过 Skill 完成了实际离线计划和核对。Easel 包装器真实发帖是独立验收结果。新增测试通过；全量本地 Windows 测试仍有与基线一致的 21 项失败，不宣称全库全绿。

上游[逐项验收记录](https://github.com/HSJ-BanFan/xiaoheihe-api-collect/blob/main/docs/skill-kit-acceptance.md)区分测试范围和未验证项。
