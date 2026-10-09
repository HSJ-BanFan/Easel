# 小黑盒 Skill 与 CLI

小黑盒集成走 `Skill + CLI`，不启动 MCP。Easel 的聊天、技能列表和 `easel skill` 可以发现 `skill-xiaoheihe-publisher`。这是 AI 技能入口，不是 Web 原生账号页或发布页的新平台按钮。

## 使用

Python 3.10+ 可运行仓库自带 CLI，无需全局安装 `xhh-sdk`。Windows x86_64 用户提供受支持的 APK 后，一条命令导入并测试签名器；不需要 Maven、Git、JDK 或模型服务。

在 Easel 根目录运行：

```console
python skills/shared/scripts/xiaoheihe_setup.py --apk "<用户APK路径>" --install-java --confirm
```

程序下载固定版本的预编译 JAR 与依赖并核对哈希。已有 Java 17+ 时可省略 `--install-java`；否则该选项允许下载私有 JRE，不改系统配置。
要绑定已有账号，增加 `--account <已有账号别名>`。不指定账号就只安装签名器，不登录、不发送短信、不发布。`ready` 只表示实际合成签名自检通过。
已有缓存可用 `--offline` 重试；自备 Java 可用 `--java "<java可执行文件>"`。复制后的 OpenClaw 工作区用 `python shared/scripts/xiaoheihe_setup.py`，或在任意目录使用包装器的完整路径。
平台范围、账号库选择及完整步骤见[技能设置](../skills/openclaw/skill-xiaoheihe-publisher/references/setup.md)。账号和 APK/目标 SO 不随仓库分发，真实账号操作仍由原 CLI 的 Windows DPAPI 存储管理。

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

- 内置 `xhh-publisher-kit 0.2.0rc1`，原 CLI `0.5.0rc4+standalone.7`。
- 原 CLI 的 25 个 wheel 成员逐字节保留，`vendor/SOURCE.json` 记录完整来源和文件哈希。
- Kit 修正图片提交形态，先上传冻结图片，再把返回 URL 与尺寸写入 HTML 正文，最后调用原 CLI 发帖。
- 快照升级使用[完整同步命令](../skills/openclaw/skill-xiaoheihe-publisher/EASEL-META.md)，提供 `--from` 和 `--source-commit`；检查用 `python scripts/sync_xiaoheihe_kit.py check`。不要手改 vendor。
- 上游工具包采用 MIT，Easel 适配采用本仓库 Apache-2.0；预编译签名器中的第三方代码按其发布许可与声明提供，不把全部依赖称为 MIT。Easel vendor 只包含文本，不保存 JAR、JRE、APK 或 SO。

## 本轮验收

2026-10-09 从公开 Release 的 0.2.0rc1 工具包验证预编译安装。空缓存与无 Java/JDK/Maven 的 PATH 下自动安装私有 JRE 17，真实签名匹配，重复安装复用同一 bundle，移走 APK 后仍可签名。Easel 设置包装器绑定测试账号的隔离副本，重复执行不改账号修订，原账号库保持不变。测试账号通过 App 身份核验、服务器草稿列表核对，以及公开短文本的提交、本人列表和 read 核对；创建内容均已删除并确认消失。63 项集成测试通过。

本次未重新发送短信、上传图片或验证匿名可见性。通用 read 不读取草稿全文，短文本摘要匹配也不能代表长文章全文验收。以下图文证据来自上一版本，不混作本轮结果。

2026-10-08 的 0.1.0rc1 使用测试账号通过 Easel 包装器完成公开模式图文发布。编辑读回确认完整中文、emoji 和图片保留；另一登录账号可以读取同帖。CDN 将图片转为 WebP，尺寸和画面已核对。测试帖子与草稿均删除后确认消失。上传对象无支持的删除接口，可能继续保留。

本轮复用已有 App 会话，并非重新完成短信登录。匿名网页触发 CAPTCHA，未证明未登录访问。自动回执仍为 `acknowledged`，不把有限列表核对伪装成全量验证。

本机 OpenClaw 模型服务返回 HTTP 401，模型自主执行演示未通过；独立 AI 消费者通过 Skill 完成了实际离线计划和核对。Easel 包装器真实发帖是独立验收结果。新增测试通过；全量本地 Windows 测试仍有与基线一致的 21 项失败，不宣称全库全绿。

上游[逐项验收记录](https://github.com/HSJ-BanFan/xiaoheihe-api-collect/blob/main/docs/skill-kit-acceptance.md)区分测试范围和未验证项。

安全边界：设置器按发布锁校验实际 JAR，但原 `.7` 日常调用信任本地 bundle manifest。不能防止 manifest 与 JAR 同时被恶意替换，也不是操作系统沙箱。请保护用户运行目录，不允许不可信进程写入。
