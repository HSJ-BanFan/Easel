# Easel SKILL 元数据

| 字段 | 值 |
|------|-----|
| SKILL 名称 | skill-xiaoheihe-publisher |
| 所属层 | publish |
| 来源类型 | 自研 Easel 门禁与文档，原字节内置上游发布工具包 |
| 原始来源 | [HSJ-BanFan/xiaoheihe-api-collect](https://github.com/HSJ-BanFan/xiaoheihe-api-collect) |
| 工具包版本 | xhh-publisher-kit 0.1.0rc1 |
| CLI 版本 | xhh-sdk 0.5.0rc4+standalone.7 |
| 许可 | Easel 适配遵循 Apache-2.0；上游许可见 vendor/xiaoheihe-publisher/LICENSE 及 runtime 内许可证 |
| 精确快照 | vendor/SOURCE.json 记录上游提交、原 wheel 哈希、manifest 哈希及所有文件哈希 |

原版 CLI 未修改。`vendor/xiaoheihe-publisher/` 由上游构建输出生成，不手工编辑。
Easel 只增加输出路径检查、出站内容门禁与 `--exec` 到 `--confirm` 的映射。
不引入 MCP、账号存储、私有签名二进制或原生 Web 平台后端。

## 同步与检查

在上游按其构建文档生成工具包后，在 Easel 根执行以下命令。`<构建目录>` 是完整的 `xiaoheihe-publisher` 目录，不是仓库源目录或 ZIP。

```bash
python scripts/sync_xiaoheihe_kit.py sync --from <构建目录> --source-commit <上游完整提交SHA>
python scripts/sync_xiaoheihe_kit.py check
```

同步检查允许的文件、每个文件哈希、版本和原 wheel 哈希，并重新生成 `SOURCE.json`。
已有快照被修改时拒绝覆盖，先人工审阅并恢复或迁移本地修改。
Git 属性关闭 vendor 文件的换行转换，保留上游字节。
本地校验只证明来源与字节一致，不证明在线登录、上传、发帖或平台可见性。
