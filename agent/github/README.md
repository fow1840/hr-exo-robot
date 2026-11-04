# GitHub 工单配置

## 工单模板

模板源文件必须位于仓库的 `.github/ISSUE_TEMPLATE/`，否则 GitHub 无法在新建 Issue 页面自动识别。

- `.github/ISSUE_TEMPLATE/ai-task.yml`：通用 AI 工单。
- `.github/ISSUE_TEMPLATE/deployment.yml`：打包与真机部署工单。
- `.github/ISSUE_TEMPLATE/config.yml`：禁止绕过模板创建空白 Issue。

模板内容属于 Agent 协作体系，但为了保持 GitHub 功能，不能物理移入 `agent/`。
