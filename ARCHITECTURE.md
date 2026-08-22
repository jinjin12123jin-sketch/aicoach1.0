# ARCHITECTURE

```text
Streamlit UI
    │
    ├── Workflow Studio
    │      ↓
    │   User Query
    │      ↓
    │   Deterministic Risk Precheck
    │      ↓
    │   LLM Router
    │   Task + Prototype + Parameters
    │      ↓
    │   Policy Engine
    │   allow / guardrail / refuse / escalate
    │      ↓
    │   Retrieval Dispatcher
    │   P01 → 非时长单项指标
    │   P02 → 时间点/时长
    │   P05 → 多指标 + 7次个人基线
    │   P07 → 受控睡眠术语库
    │   P11/P12 → 周期趋势/个人基线
    │   P14 → 睡眠同域综合分析
    │   P25 → 高风险分流（预检直接返回）
    │      ↓
    │   Reusable Insight Engine
    │   Evidence + Priority + Approved Claims
    │      ↓
    │   P02 Answer Planner
    │   Required Facts + Default Companions
    │   + Controlled Candidate Insights + Style Policy
    │      ↓
    │   Candidate LLM
    │      ↓
    │   P02 Response Validator
    │   Grounding + UX Wording + Safety Boundary
    │   (失败时携带错误原因重写一次)
    │      ↓
    │   AI Coach Answer
    │
    └── Evaluation
           ↓
       Expected Routing
       Expected Parameters
       Expected Retrieval
       Ground Truth
       Rubrics
           ↓
       LLM Judge
           ↓
           Routing Score + Retrieval Score
           + Response Score + Explanation
```

## 可观测工作流层

`backend/workflow_trace.py` 将一次回答记录为统一的Node Trace：

```text
run
├── schema_version / started_at / duration_ms
└── nodes[]
    ├── id / title / category / source files
    ├── status: pending / running / success / blocked / skipped / error
    ├── input / output
    ├── started_at / ended_at / duration_ms
    └── meta.model_call: model / attempts / usage / duration
```

节点与文件映射由 `config/workflow_modules.json` 声明。业务节点代表实际产品步骤；同一个Python或JSON可以同时挂载到多个节点。界面从注册表自动展开源码目录，并自动把未归类的Python/JSON放入“其他实现资源”，从而保证项目文件可发现，但不把每个文件错误地画成独立运行节点。

Workflow Studio采用只读模式：可以查看Messages、原始模型输出和传递数据，但不能修改源码、配置或执行连线；敏感字段在Trace层统一脱敏，`.env`禁止读取。

Candidate LLM 不会看到 `evaluator_only`、Ground Truth、Rubric。
这些只在评测阶段读取。

P02 的 Candidate LLM 也不会直接接收全部原始睡眠记录，而只接收 `Answer Plan`。程序负责算数、个人基线、显著性和关系权限，LLM 负责把允许内容组织成自然语言；`backend/response_validator.py` 再检查必答值、默认信息、报告腔、内部元数据和无依据状态评价。Python 不拼接最终用户话术。

原型由 `config/prototypes.json` 注册；Case 会从 `bench/**/*.json` 动态发现，Rubric 按各 Case 的 `rubric_files` 动态加载。

## 回答能力的分层

```text
共享能力层：数据口径、指标计算、基线、洞察候选、证据、健康表述白名单
                         ↓
原型编排层：P01/P02/P05/P07/P11/P12/P14/P25分别组织回答合同与Rubric
```

因此多个原型可以复用相同的数据、个人基线和洞察计算，但不复用完全相同的回答模板。P07与个人数据原型不同：它先从受控JSON术语库检索词条，再让模型按“定义 → 如何理解 → 设备限制”组织表达。新增原型通常需要定义自己的回答合同和Rubric，但不一定需要重写底层计算。

P02 进一步使用四个指标族复用回答策略：睡眠边界、总体时长、睡眠阶段、连续性相关时长。用户措辞先被 Router 归一为标准字段，再由 `config/metric_profiles.json` 决定默认信息包，不为每个问法维护固定答案。

## Answerability 流程

`backend/prompts.py` 只生成给模型看的分类指令；模型执行语义分类，`backend/router.py` 校验结构，`backend/policy_engine.py` 才根据 `config/answerability_rules.json` 作最终决策。紧急风险、诊断和用药中的明显关键词会在调用模型前被确定性预检拦截。
