# GitHub Issues 工单规范

仓库：`fow1840/hr-exo-robot`。

## 必需标签

- 状态：`status:ready`、`status:in-progress`、`status:review`、`status:acceptance`、`status:blocked`
- 优先级：`priority:p0`、`priority:p1`、`priority:p2`、`priority:p3`
- 类型：`type:feature`、`type:bug`、`type:diagnosis`、`type:deployment`、`type:docs`
- 证据：`evidence:static`、`evidence:offline`、`evidence:target-runtime`、`evidence:robot-accepted`

## 认领

```bash
gh issue view <n> --comments
gh issue edit <n> --add-assignee @me --remove-label status:ready --add-label status:in-progress
gh issue comment <n> --body "已认领。范围：...。预计产出：...。"
```

Issue 已有 assignee 或 `status:in-progress` 时，其他 AI 不得写入同一范围。

## 交付评论模板

```markdown
## 交付
- 范围：
- 改动：
- Commit/PR：
- 验证命令：
- 验证结果：
- 证据等级：静态 / 离线 / 目标机运行 / 真机验收
- 未验证：
- 风险：
- 回滚：
- 请 donghai 验收：
```

## 关闭

真机工单只有在 donghai 明确回复验收通过后才关闭，关闭评论必须保留原始验收结论。
