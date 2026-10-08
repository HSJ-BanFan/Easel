# 配置真实账号与签名

Python 3.10+ 运行随包原版 CLI，无需全局安装 xhh-sdk。
在线签名还需要用户自备 Java 17+ 和有权使用的签名资源或可信 JAR。
包不含这些二进制，也不包含账号、手机号、验证码或默认身份。
离线规划与查看支持跨平台。当前原版账号存储使用 Windows DPAPI，真实账号登录与发布受此平台限制。

## 找到执行路径

推荐设置 `EASEL_ROOT` 为本机 Easel 项目根，在该根目录执行下列命令。
源码版 CLI 位于 `skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py`。
OpenClaw 同步副本位于工作区的 `skills/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py`；共享包装器在 `shared/scripts/xiaoheihe_publish.py`。
包装器以 `EASEL_ROOT` 为准；未设置时按自身文件位置发现源码或工作区内的工具包，不依赖当前工作目录。
工作区的 `outputs` 应按 Easel 正常同步方式指向项目输出。不要通过重装或修改全局配置绕过路径失败。

## 检查与登录

```bash
python skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py --version
python skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py doctor --offline
python skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py signer --help
python skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py account list
python skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py account login <账号别名> --method sms --phone <用户手机号> --confirm
python skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py account status <账号别名> --online
```

登录是真实线上操作，会发送短信。用户先确认手机号与账号别名，在本地输入验证码，不把号码或验证码写入 spec、报告或提交记录。
尚未绑定身份的别名按上游配置说明提供用户自己的数字身份 ID；验证码通过再次调用登录命令并加 `--code <本次验证码>` 完成校验。
账号加密存储由原 CLI 管理；不复制账号库、不读取密文、不从 Profile 推断账号。
签名配置按随包 [上游配置说明](../vendor/xiaoheihe-publisher/references/setup.md) 执行。先查看 `signer --help` 和对应子命令帮助，不猜参数。
`doctor --offline` 通过不表示在线会话有效；需要 `account status <账号别名> --online` 的实际结果。
已有会话验证成功不等于重新完成了一次短信登录。

## 单独上传图片

用户确认具体账号和图片后，可调用原 CLI 执行真实上传。

```bash
python skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py --account <账号别名> upload outputs/<具体主题>/cover.png --confirm
```

上传成功不等于发帖成功。通常不必单独上传，发布工具包会在执行已确认计划时上传冻结的本地图片。
账号文件、私有签名资源和敏感参数只在本机使用，禁止提交到 Git 或发布包。
