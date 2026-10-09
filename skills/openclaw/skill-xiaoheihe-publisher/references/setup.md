# 配置真实账号与签名

Python 3.10+ 运行随包原版 CLI，无需全局安装 xhh-sdk。
在线签名需要用户有权使用的受支持 APK。下面的一条命令完成本地导入、预编译签名器下载与签名自检，不要求安装 Maven、Git 或 JDK。
包不含 APK、目标 SO、账号、手机号、验证码或默认身份。签名器 JAR 和可选 JRE 在本机下载并核对固定版本、大小与 SHA-256。
离线规划与查看支持跨平台。当前原版账号存储使用 Windows DPAPI，真实账号登录与发布受此平台限制。

## 找到执行路径

推荐设置 `EASEL_ROOT` 为本机 Easel 项目根，在该根目录执行下列命令。
源码版 CLI 位于 `skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py`。
OpenClaw 同步副本位于工作区的 `skills/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py`；共享包装器在 `shared/scripts/xiaoheihe_publish.py` 和 `shared/scripts/xiaoheihe_setup.py`。
包装器以 `EASEL_ROOT` 为准；未设置时按自身文件位置发现源码或工作区内的工具包，不依赖当前工作目录。
工作区的 `outputs` 应按 Easel 正常同步方式指向项目输出。不要通过重装或修改全局配置绕过路径失败。

## 一条命令导入 APK

当前安装器支持 Windows x86_64。准备 Python 3.10+ 和自己提供的受支持 APK，在 Easel 根目录运行。无需启动 Easel、OpenClaw 或模型服务。

```bash
python skills/shared/scripts/xiaoheihe_setup.py --apk "<用户APK路径>" --install-java --confirm
```

已有 Java 17+ 时省略 `--install-java`，或用 `--java "<java可执行文件>"` 明确指定。
`--install-java` 仅在没有合适 Java 时允许下载固定版本的私有 JRE，不安装系统软件，也不改 PATH 或 JAVA_HOME。
不传 `--confirm` 不执行导入。确认范围只包括本地资源导入、固定依赖下载及合成签名自检，不包括登录、短信、上传或发帖。
安装器先拒绝不受支持的 APK，再下载依赖；不会上传 APK。受支持文件以随包校验常量为准，不接受任意新版 APK。

要同时绑定一个已经存在的账号别名，显式加上 `--account`。自检通过后才更新该别名的 `signer_bundle` 和 `java`，保留原身份、会话、其他配置与默认账号。

```bash
python skills/shared/scripts/xiaoheihe_setup.py --apk "<用户APK路径>" --account <已有账号别名> --install-java --confirm
python skills/shared/scripts/xiaoheihe_setup.py --apk "<用户APK路径>" --offline --confirm
```

没有 `--account` 时只安装签名器，不创建账号、不登录。`--offline` 只复用哈希验证通过的缓存，缺少或损坏时拒绝，不补下载。
源码之外运行时使用包装器的完整路径；OpenClaw 工作区副本改用 `python shared/scripts/xiaoheihe_setup.py`，参数不变。

标准输出是一个 JSON 对象。只有真实合成签名与固定参考值匹配后才返回 `state: ready`；它不表示账号已登录、网络可用或允许发布。
`state: refused` 时按原因处理后重试，不手改缓存哈希或 release lock。下载和 Java 进程超时由随包安装器管理。
安装资源默认放在用户目录的 `.xhh_sdk` 下；`XHH_SETUP_HOME` 可指定绝对缓存路径，`XHH_BUNDLE_HOME` 可指定实际 bundle 存储。不要将这些目录指向仓库。

`--data-dir` 只选择本次绑定使用的原 CLI 账号库，不会切换 Easel 发布器的账号库。普通发布使用默认账号库；只在明确使用独立账号库时传此参数，后续原 CLI 命令也必须指定相同 `--data-dir`。
没有现成账号时先进行不带 `--account` 的签名器安装，再按原 CLI 账号配置流程创建自己的别名，最后重新运行带 `--account` 的安装命令。不要由模型推断身份或自动新建别名。

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
账号创建、身份配置与手动诊断见随包 [上游配置说明](../vendor/xiaoheihe-publisher/references/setup.md)。先查看对应子命令帮助，不猜参数。
`doctor --offline` 通过不表示在线会话有效；需要 `account status <账号别名> --online` 的实际结果。
已有会话验证成功不等于重新完成了一次短信登录。

## 单独上传图片

用户确认具体账号和图片后，可调用原 CLI 执行真实上传。

```bash
python skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_cli.py --account <账号别名> upload outputs/<具体主题>/cover.png --confirm
```

上传成功不等于发帖成功。通常不必单独上传，发布工具包会在执行已确认计划时上传冻结的本地图片。
账号文件、私有签名资源和敏感参数只在本机使用，禁止提交到 Git 或发布包。
