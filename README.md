# task-retrospective

`task-retrospective` 把已完成任务的能力审计与实际升级拆成两个需要人类阅读的阶段：

1. 复盘一：只读重建、能力审计、反事实和改进提案。
2. 人类阅读后明确说“继续”：复盘二才实施 Agent 侧修复、建设 Human–Agent 协作手册、主会话验收和环境清理。

明确要求“轻量经验检查”或“只提炼返工教训”时走只读短路径，不初始化手册、不进入复盘二；方法见 [轻量经验检查](references/lesson-check.md)。完整双阶段协议保持原有人工阅读停点。

入口：[SKILL.md](SKILL.md)

本仓库用于公开参考。技能依赖当前 Agent 环境中的 `asm`、`dev` 等协作能力；其中的 ASM 更新检查入口需要另行安装，单独克隆本仓库不代表已经具备全部运行依赖。测试中的 `example.test` 地址和示例凭据用于拒绝路径验证，不是真实账号配置。

运行参数：

- 完整双阶段复盘首次启动读取技能真实目录内的 `.local/config.json`；没有保存目标时询问一次并保存，以后跨目录、跨会话复用。配置不进入 Git，源码更新保留本机配置；新设备的全新安装各自初始化。
- `HUMAN_AGENT_PLAYBOOK_TARGET`：可选的本次覆盖。缺失或空字符串都使用已保存目标；明确要求更换默认目标时才更新保存值。
- Agent 使用 `scripts/playbook_settings.py get` 读取，使用 `set --target <目标>` 首次保存。目标只能来自当前明确选择或已保存配置，历史模板路径只是候选。读配置不创建手册、不授权复盘二或远程发布。

Python 3 为运行依赖；Linux 下配置 CLI 和 Git fast-forward 保留已验证。复制安装、删除重装、Windows / macOS 实机与其他模型行为分别未验证。

维护验证：`python3 scripts/validate_delivery.py --asm-root <ASM 的真实目录> --output <报告相对路径>`，合同也使用同一入口；静态触发结果只证明启发式检查。 公开版保留通用技能、脚本、测试和脱敏设计依据；内部任务状态、交接材料、验证日志及本机配置不随公开版发布。

复盘二写集检查：`python3 scripts/check_write_scope.py --allow <允许根绝对路径> --protect <冻结根绝对路径> --write <计划文件绝对路径>`；参数可重复。该只读检查拒绝越界与冻结目录重叠，包括写入冻结目录的祖先和解析后指向冻结目录的链接。它不执行修复、不改变权限，也不保证后续任意命令受隔离。“继续复盘二”仍保留当前有效的禁止修改范围。

复盘一答复结构检查：`python3 scripts/check_phase_one.py --answer <答复文本文件>`。它只证明能力沉淀决定段落、词表、查重依据和授权状态存在，不判断决定是否合理，也不证明答复已送达用户；真实遗漏样例在 `tests/fixtures/phase-one-missing-decision.md`。

历史案例与设计依据见：[references/case-evidence.md](references/case-evidence.md)。
