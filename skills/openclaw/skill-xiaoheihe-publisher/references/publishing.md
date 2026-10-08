# 发布与核对契约

## 发布 spec

JSON 只接受 `title`、`content`、`content_format`、`hashtags`、`topic_ids`、`images`、`post_type`、`original`。
标题和正文为字符串；`content_format` 是 `text` 或 `html`，`hashtags` 是字符串数组，`topic_ids` 是仅含 ASCII 数字的字符串数组。
`images` 是本地图片路径数组，相对路径以 spec 所在目录为准。`post_type` 是 1 或 3，`original` 是布尔值。
工具包会检查实际字段与图片再创建操作目录。精确限制以 [上游发布说明](../vendor/xiaoheihe-publisher/references/publishing.md) 为准。

```json
{
  "title": "独立游戏体验记录",
  "content": "这一关的节奏设计与配乐配合自然。",
  "content_format": "text",
  "hashtags": ["独立游戏"],
  "images": ["../cover.png"],
  "post_type": 1,
  "original": true
}
```

账号和模式通过 CLI 参数指定，不放入 JSON。`cover_url`、`visibility`、远程图片或其他未知字段不能用于此冻结流程。
特殊格式仍保留在原版 CLI 中，但 AI 发布不可用它绕过 Easel 内容门禁和用户确认。

## 真实发帖

使用 `--mode public` 准备公开帖子，使用 `--mode draft` 准备服务器草稿。
两种模式在 `submit` 时都会产生线上写入；`plan`、`show` 不上传或访问凭据。

```bash
python skills/shared/scripts/xiaoheihe_publish.py plan outputs/<具体主题>/assets/post.json --account <账号别名> --mode public --out outputs/<具体主题>/assets/<新操作目录>
python skills/shared/scripts/xiaoheihe_publish.py show outputs/<具体主题>/assets/<新操作目录>
python skills/shared/scripts/xiaoheihe_publish.py submit outputs/<具体主题>/assets/<新操作目录> --approval <用户确认的摘要> --exec
python skills/shared/scripts/xiaoheihe_publish.py reconcile outputs/<具体主题>/assets/<新操作目录>
```

提交前展示完整计划并取得用户确认。摘要绑定账号、模式、内容、图片与运行时。
Easel 对 `show` 返回的冻结标题、正文、标签执行 `content_guard.guard_or_die`，随后将同一摘要传给工具包。
改变原图片不改变已冻结副本；改变操作目录内图片、计划或工具包会被校验拒绝。
工具包负责显式账号在线验证、真实上传和单次发布调用；Easel 不另写 SDK 或处理账号存储。

## 回执语义

| state | 可报告的事实 |
|-------|--------------|
| prepared | 本地计划已准备，无线上写入 |
| acknowledged | 服务端创建已应答，尚未验证完整结果或公开可见性 |
| verified_draft | 已按回执证据验证自己的服务器草稿 |
| verified_public | 仅按回执明确说明的证据范围报告验证结果 |
| outcome_unknown | 可能已写入，禁止重试；只读核对自己的草稿或帖子 |
| refused | 校验或权限门禁拒绝，按具体回执处理 |

退出码 0 也可能只是 `acknowledged`，不能据此标记公开发布成功。
退出码 2 表示拒绝，3 表示结果未知，Easel 内容门禁以 7 阻止敏感信息外发。
`reconcile` 只核对现有操作，不创建新帖子，不清除 `attempt.json`。
一个操作目录最多调用一次发布，不是服务端全局 exactly-once。账号配置在外部并发改变仍属于明确限制。
只有自己的帖子读回证据不一定能证明公众可见；如无法取得相应证据，保持 `acknowledged` 并说明限制。
