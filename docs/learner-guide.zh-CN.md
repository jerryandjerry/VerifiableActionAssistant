# 学员学习指南：如何把这个项目讲成一个 L4 Applied AI 项目

## 一、项目的核心不是“做了一个 Agent”

这个项目真正要证明的是：你能够把不确定的模型能力，放进一个可控的软件系统里。
面试时不要把重点放在用了多少 Agent、多少 Prompt 或多少框架，而要讲清楚五件事：

1. **系统边界在哪里**：模型只负责结构化分析，不能授权、审批或直接写外部系统。
2. **证据如何成立**：每个 Claim 都要映射到当前版本的具体文档、章节和摘录。
3. **副作用如何受控**：任何写操作都必须经过权限检查、预览和人工批准。
4. **失败如何恢复**：外部 API 超时不等于失败，必须先对账，再决定是否重试。
5. **升级如何防回归**：模型、Prompt 或检索变化都要经过测试集和 Eval Gate。

## 二、建议的代码阅读顺序

### 第一步：先看状态机

阅读 `src/vaa/services/orchestrator.py`，理解任务为何不是一次性的：

```text
请求 → 合同 → 检索 → 验证 → 提案 → 审批 → 执行 → 确认
```

重点观察每次状态变化都会写数据库和 Audit Event。

### 第二步：看权限和工具边界

阅读：

- `services/policy.py`
- `services/tool_gateway.py`
- `tools/fake_jira.py`

回答三个问题：

- 为什么不能只在 System Prompt 里写“未经允许不要调用工具”？
- 为什么读权限、写权限和审批权限要拆开？
- 为什么 API 超时之后不能直接 Retry？

### 第三步：看证据链

阅读：

- `services/retrieval.py`
- `services/analyzer.py`
- `services/verifier.py`

注意系统不是简单做 RAG，而是在建立：

```text
Claim → Observed Values → Source IDs → Versions → Conflicts
```

### 第四步：看攻击与回归测试

阅读 `tests/` 和 `evals/dataset/cases.jsonl`。尤其关注：

- 跨租户访问为什么返回 403；
- 恶意文档为什么不能扩大工具权限；
- 拒绝审批后为什么 Ticket 数量必须是 0；
- Timeout After Success 为什么 Ticket 数量仍然只能是 1；
- Pause After Approval 为什么可以恢复。

## 三、建议的二次开发任务

### 基础升级

- 为 `TaskContract.budgets` 增加真正的 Runtime Enforcement；
- 为 `Document` 增加内容 Hash 和有效期；
- 为 Evidence Ledger 增加 Source Authority 排序；
- 增加“证据不足时询问用户”的 Clarification 状态；
- 在 UI 中加入 Source Detail Drawer。

### 中级升级

- 把 Lexical Retrieval 升级成 BM25 + Embedding Hybrid Search；
- 接入真实 Jira Sandbox，但保留 Idempotency 和 Reconciliation；
- 增加 OpenTelemetry Trace；
- 用 PostgreSQL 跑并发审批与重复请求测试；
- 增加 Policy-as-Code 层。

### Hard Mode

- 把状态机迁移到 Temporal 或 DBOS；
- 设计 MCP Tool Gateway，但不允许 Token Passthrough；
- 加入多轮审批、审批过期和撤销；
- 构建 100 条以上的 Prompt Injection 与 Tool Misuse Eval；
- 做一次 Model Upgrade Canary，比较质量、成本、P95 延迟和失败类型。

## 四、面试时的三分钟讲法

> 我做的不是一个普通 RAG Chatbot，而是一个可以在项目交付场景中执行受控动作的
> Reliable Assistant。系统先根据任务风险选择 Read、Verified Research 或 Controlled
> Action Lane，再生成一个包含 Scope、Allowed Tools、Evidence Requirement、Approval
> Policy 和 Budget 的 Task Contract。模型只负责结构化分析，权限、审批、工具调用、
> 幂等和执行后确认都由普通代码完成。
>
> 我特别实现了两个生产系统里常见但 Demo 经常忽略的失败场景。第一，外部文档中
> 包含 Prompt Injection 时，文档只被视为不可信数据，不能扩大权限或工具范围；第二，
> Jira 已经创建 Ticket 但响应超时，系统不会盲目重试，而是进入 Reconciliation，使用
> Idempotency Key 查询外部状态，最终保证只产生一个可见副作用。
>
> 最后，我用单元测试和八个端到端 Eval 覆盖路由、证据、审批、拒绝、跨租户隔离、
> Prompt Injection、Timeout Recovery 和 Durable Resume，确保模型或 Prompt 升级不会
> 破坏系统不变量。

## 五、不要夸大的地方

面试时应主动说明：

- 当前检索器是可解释的本地基线，不是生产级 Hybrid Retrieval；
- Jira 是数据库模拟器，不是真实 SaaS Integration；
- Prompt Injection Scanner 只是 Defense in Depth，不代表免疫；
- Durable State 已落库，但生产多 Worker 场景仍应引入专业 Workflow Engine；
- 当前 Eval 是小型回归集，真正上线前需要扩大到领域数据和对抗样本。

这种诚实不会削弱项目，反而能体现你知道 Demo、Reference Implementation 和生产系统
之间的边界。
