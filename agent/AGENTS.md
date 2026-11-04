# HR-EXO-robot Agent 工作规则

## 用户与沟通

- 称呼用户为 donghai。
- 先确认对象、复现条件、范围和验收目标，再开始修改。
- 遇到设备、真机状态、接口或现象不清楚时，优先请 donghai 提供资料，不猜测。
- 明确区分源码/静态/离线证据与真机运行证据。

## 工单与多 AI 协作

- GitHub Issues 是唯一动态工单源，规范见 `agent/issue-tracker.md`。
- 一次只处理一张工单；开工前必须先读完工单及评论。
- 一个工单只有一个主写者。其他 AI 可以做只读分析、证据整理和代码审查。
- 开工时给工单分配自己，并加 `status:in-progress`；发现已被认领就停止写入。
- 收工时在工单中写明改动、commit、验证证据、风险、回滚和下一步。
- AI 不得自行宣布真机验收通过；只有 donghai 确认后才能关闭工单。

## 代码与真机安全

- 工作前先读 `agent/AI_PROTOCOL.md`、对应 Issue、`agent/HANDOVER.md` 和相关部署文档。
- 不覆盖未知来源的本地改动，不使用破坏性 Git 命令。
- 所有真机操作顺序：当前状态 → 复现 → 保留证据 → 离线验证 → 最小改动 → 分阶段真机验收。
- 未明确命令话题、关节名称/顺序/符号、限位、控制频率、会话门控和急停机制前，不允许下发真机运动命令。
- 编译、静态检查和仿真通过不等于真机验收。

## 项目文档

- 工单规范：`agent/issue-tracker.md`
- 技术交接：`agent/HANDOVER.md`
- 问题台账（问题/根因/处置追溯）：`agent/LEDGER.md`
- 部署门禁：`agent/deployment.md`
- 领域词汇：`agent/GLOSSARY.md`
- GitHub 配置：`agent/github/`
- 架构决策：`agent/adr/`
