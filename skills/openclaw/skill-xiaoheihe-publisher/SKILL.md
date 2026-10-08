---
name: skill-xiaoheihe-publisher
description: >-
  当用户要登录小黑盒账号、上传自己的图片、预览小黑盒图文、保存服务器草稿或确认公开发帖时使用。
  通过随包原版 CLI 管理账号与签名，通过 Easel 门禁冻结并提交经确认的内容，支持结果核对且不自动重发。
  不用于其他平台、批量互动或原生 Web 账号管理页；离线计划不等于已上传、已发帖或公开可见。
layer: publish
---

# 小黑盒发布

通过随包 CLI 执行真实登录、图片上传与发布。Python 3.10+；不需要全局安装 xhh-sdk，不使用 MCP。

## 输入

- 用户明确选择的本地账号别名，不读取默认账号。
- 标题、正文、标签及本地图片，保存为非敏感 JSON。
- 明确的 `draft` 或 `public` 意图。服务器草稿也属于线上写入。

## 输出

写入 `outputs/<具体主题>/assets/<操作目录>/` 的冻结计划、图片副本和回执。
`acknowledged` 只表示创建得到应答。公开可见与内容一致需要独立核验，当前工具包不输出完整验证状态。
本技能不自动写发布日历。

## 执行步骤

1. 先确认 `EASEL_ROOT` 并在 Easel 项目根执行文档命令。工作区副本的路径说明见 [运行与账号](references/setup.md)。
2. 首次使用先读 [运行与账号](references/setup.md)。用随包 `vendor/xiaoheihe-publisher/scripts/xhh_cli.py` 检查版本、配置用户自备签名资源并完成真实登录；不要把手机号、验证码、账号存储或签名资源放入项目。
3. 整理非敏感发布 spec。格式和结果语义见 [发布与核对](references/publishing.md)。每次新内容使用新操作目录。
4. 先离线冻结，未执行上传或发布。

```bash
python skills/shared/scripts/xiaoheihe_publish.py plan outputs/<具体主题>/assets/post.json --account <账号别名> --mode draft --out outputs/<具体主题>/assets/<操作目录>
python skills/shared/scripts/xiaoheihe_publish.py show outputs/<具体主题>/assets/<操作目录>
```

5. 展示实际 `show` 返回的账号、模式、全文、标签、图片和 `approval_sha256`。公开发帖必须用 `--mode public` 重新生成计划，不能修改冻结文件或复用旧批准。
6. 用户确认上述具体计划后才执行。`--exec` 只转换为底层 `--confirm`，不代替用户确认。Easel 会再次检查冻结计划及出站内容。

```bash
python skills/shared/scripts/xiaoheihe_publish.py submit outputs/<具体主题>/assets/<操作目录> --approval <已确认摘要> --exec
python skills/shared/scripts/xiaoheihe_publish.py reconcile outputs/<具体主题>/assets/<操作目录>
```

7. 超时、失去应答、`outcome_unknown` 或已有提交记录时不重发，也不删除 `attempt.json`。先只读核对自己的草稿或帖子，再向用户说明未验证范围。

## Profile 感知

Profile 可提供语言风格与受众，不可提供或推断账号凭据。没有 Profile 也可使用。
账号别名始终由用户指定；新账号登录和签名配置仍交给随包原版 CLI。

## 边界

- Skill 可从 CLI、Web 技能列表和聊天发现，不接入 Web 原生发布页或账号页。
- 自动发布只能走 Easel 门禁。原版 CLI 保留账号、签名和特殊格式功能，但不作为跳过门禁的捷径。
- 不批量点赞、评论或操纵他人内容；不自动下载远程图片。
- 完整上游代码保持原字节。来源与更新见 [EASEL-META.md](EASEL-META.md)。
