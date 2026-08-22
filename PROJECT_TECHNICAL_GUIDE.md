# AI Coach Lab v0.1 技术学习手册

> 适用项目：`D:\download\ai-coach-lab-v0.1`  
> 目标读者：有编程基础，但不熟悉 Python、Streamlit 与 LLM Eval 架构的开发者  
> 文档原则：先建立全局模型，再沿真实执行链逐文件精读。

## 阅读前先看：产品经理控制台

如果你以产品经理身份参与这个项目，最重要的不是先掌握所有 Python 语法，而是先分清三类决策：

1. 哪些内容可以由产品直接调整。
2. 哪些内容需要产品、算法、医学、法务共同确认。
3. 哪些内容必须通过工程和合规机制实现，不能只改 Prompt。

### A. 产品可以主导修改的区域

| 文件或位置 | 产品可以决定什么 | 修改后的影响 |
|---|---|---|
| `backend/prompts.py` 的 `COACH_SYSTEM` | 回答顺序、语气、篇幅、是否先说结论、强调个人基线 | 改变 Candidate 的表达和信息选择 |
| `backend/prompts.py` 的 `ROUTER_SYSTEM` | 意图名称、支持范围、Out-of-scope 描述 | 改变模型如何理解问题，但不等于形成可靠的硬规则 |
| `backend/prompts.py` 的 `JUDGE_SYSTEM` | Judge 的判定任务和解释方式 | 改变评测行为 |
| `config/p05_rubrics.json` | 什么是好回答、各项权重、哪些行为扣分 | 直接改变 Evaluation Score |
| `bench/*.json` | 代表性用户问题、预期路由、测试上下文 | 扩大或调整回归测试覆盖 |
| `config/product_decisions.json` | “昨晚”、基线窗口、整体判断等产品口径的登记 | 形成团队决策记录；当前不会自动改变运行代码 |
| `app.py` 中的 UI 文案 | 提示语、警告语、信息层级、结果展示 | 改变用户体验，不应改变底层医疗结论 |

产品修改 Prompt 时建议每次同时做三件事：

```text
改 Prompt
→ 补充或修改 Bench Case
→ 运行 Rubric Eval 并人工抽查 Bad Case
```

只改 Prompt、不补测试，会让产品行为发生变化但团队无法稳定感知回归。

### B. 产品可以提出方案，但不应单独决定的区域

| 决策 | 需要共同参与的角色 | 原因 |
|---|---|---|
| 哪些问题属于健康科普、健康管理、风险提示或诊疗 | 产品 + 医学 + 法务/合规 | 不同类别的责任和风险不同 |
| 睡眠异常阈值和风险等级 | 医学 + 算法 + 产品 | 阈值必须有证据、适用人群和数据质量前提 |
| 7/14/28 日基线和异常日剔除 | 算法 + 医学 + 产品 | 会实质改变个性化结论 |
| 什么情况建议就医或升级人工 | 医学 + 产品 + 运营 | 需要明确触发条件、紧急程度和用户行动 |
| 哪些健康数据发送给第三方模型 | 安全 + 隐私 + 法务 + 产品 | 医疗健康信息属于敏感个人信息 |
| 历史记录保留多久、用户如何删除 | 隐私/法务 + 安全 + 产品 | 不能只以研究方便为依据无限保存 |
| AI 输出是否可能构成医疗器械功能或互联网诊疗 | 法务/注册 + 医学 + 产品 | 取决于预期用途、声明和实际功能，不能仅凭“免责声明”规避 |

### C. 不能只靠产品改 Prompt 的区域

以下问题必须有代码、权限、流程或基础设施保障：

- API Key、加密、访问控制和密钥轮换。
- 用户同意、敏感信息最小化、查阅和删除机制。
- 高风险问题的硬拦截和人工升级。
- 处方、诊断和治疗建议的权限控制。
- 模型版本、Prompt 版本、数据版本和输出的审计记录。
- 网络失败、模型空响应、Schema 校验和降级策略。
- 医疗安全事件、用户投诉和不良事件处理流程。

Prompt 是行为引导，不是安全边界。高风险能力必须采用“模型判断 + 确定性政策 + 人工流程”的组合。

## 当前系统究竟怎样决定“回答或不回答”

当前 v0.2 实现有四层：

```text
第一层：backend/policy_engine.py 做高风险关键词预检
明显急症、诊断、用药请求不调用模型，直接执行安全策略

第二层：DeepSeek 做结构化语义分类
backend/prompts.py 只定义 task 标签和输出格式
backend/router.py 请求 DeepSeek 返回并校验 JSON

第三层：Policy Engine 做确定性决策
config/answerability_rules.json 决定 allow / guardrail / refuse / escalate

第四层：允许的 Task 才进入 Retrieval、Insight Engine 和 Candidate
```

例如“蜘蛛侠好看吗”：

```json
{
  "module": "unsupported",
  "prototype": "none",
  "intent": "out_of_scope",
  "answerability": "cannot_answer"
}
```

`policy_engine.py` 根据 `out_of_scope` 规则拒绝，`coach.py` 负责组织和执行这条链路。

所以准确说法是：

> DeepSeek 提供语言理解能力；我们通过 Prompt 定义分类标签；Python 根据标签执行产品政策。

它不是完全依靠 DeepSeek 自身能力，但语义分类仍然是概率性的。模型可能误分类、漏掉高风险表达或受上下文干扰。当前 Router 已能区分：

- 健康科普。
- 个人数据解释。
- 症状咨询。
- 疾病诊断请求。
- 用药或处方请求。
- 急症或危机信号。
- 非产品范围问题。

当前实现已扩展为P01、P02、P05、P07、P11、P12、P14和P25。健康科普中的睡眠指标名词解释可由P07回答，但知识库状态仍为未完成医学审核的产品草案；症状、诊断和用药继续执行升级或拒答。未成年人、孕产妇、含糊问题及输出后安全检查仍是下一阶段能力。

## 大健康 App 应该怎样设计“自由度”

自由度不应该设置成一个全局开关，而应该按任务风险分层。以下是建议的产品框架，不是最终法律结论：

| 层级 | 用户需求 | 模型自由度 | 建议行为 |
|---|---|---|---|
| L0 数据陈述 | “我昨晚睡了多久？” | 很低 | 只复述已验证数据和单位，不解释病因 |
| L1 健康科普 | “REM 睡眠是什么？” | 中等 | 提供通用知识，标明适用范围和不确定性 |
| L2 个性化健康管理 | “昨晚比平时怎样？” | 受约束 | 依据个人基线总结趋势，不诊断疾病，不确定时说明限制 |
| L3 风险提示/分流 | “连续胸痛要紧吗？” | 很低 | 使用医学审核过的规则和模板，提示及时就医或紧急服务，不让模型自由发挥 |
| L4 诊断、处方、治疗决策 | “我是不是某病”“帮我开药” | 默认禁止 | 转人工或合规医疗服务；不能由通用 Coach 自主完成 |

自由度应主要体现在：

- 表达方式可以自然。
- 可从已验证数据中选择重点。
- 可以提出低风险、通用且可逆的健康管理建议。
- 可以主动询问缺失信息。

自由度不应体现在：

- 自由创造医学事实。
- 猜测疾病和病因。
- 自行设置医学阈值。
- 自动生成处方。
- 用一句“仅供参考”覆盖高风险行为。

## 建议的生产级 Answerability 架构

当前 v0.2 已落地的架构：

```text
用户问题 → 高风险预检 → LLM Router → Policy Engine → 回答/拒答/升级
```

它已经比最初 Demo 多了一层确定性边界，但仍需继续演进为：

```text
用户问题与上下文
        │
        ▼
① 确定性前置安全检查
   急症关键词、处方请求、未成年人、隐私输入等
        │
        ▼
② LLM 结构化意图提取
   topic / task / risk / answerability / missing_info
        │
        ▼
③ Schema 严格校验
   缺字段、未知枚举、格式错误直接降级
        │
        ▼
④ 产品政策矩阵（代码或配置，不是 Prompt）
   哪类用户 × 哪类问题 × 哪类数据 → 允许的响应模式
        │
        ├── ALLOW：正常回答
        ├── ALLOW_WITH_GUARDRAILS：受约束回答
        ├── CLARIFY：先追问
        ├── ESCALATE：转医生/客服/紧急渠道
        └── REFUSE：拒绝高风险能力
        │
        ▼
⑤ 经过授权的数据工具
        │
        ▼
⑥ 对应风险等级的 Prompt 与模板
        │
        ▼
⑦ 输出后安全检查
   诊断词、处方、确定性因果、紧急风险遗漏
        │
        ▼
⑧ 版本化日志、抽检与不良事件闭环
```

建议 Router 输出从当前四字段扩展为：

```json
{
  "domain": "sleep",
  "task": "personal_data_summary",
  "risk_level": "low",
  "answerability": "allow_with_guardrails",
  "missing_information": [],
  "escalation_reason": null
}
```

不要盲信模型自己给出的 `confidence`。对于含糊或高风险问题，更可靠的策略是：多信号校验、明确枚举、规则覆盖、追问和人工升级。

## 产品、医学、法务如何共同维护政策矩阵

可以建立一张版本化表格：

| Domain | Task | Risk | 数据要求 | 允许输出 | 禁止输出 | 升级条件 | Owner |
|---|---|---|---|---|---|---|---|
| Sleep | 数据复述 | Low | 有当晚有效记录 | 时长、效率、趋势 | 诊断 | 数据缺失则追问/说明 | 产品+算法 |
| Sleep | 个性化解释 | Medium | 有基线且质量合格 | 谨慎总结 | 确定病因 | 连续异常或症状转人工 | 产品+医学 |
| Medication | 处方请求 | High | 不适用 | 合规引导 | 自动处方 | 转合规医疗服务 | 医学+法务 |
| Emergency | 急症信号 | Critical | 不依赖穿戴数据 | 紧急行动模板 | 长篇自由问答 | 立即升级 | 医学+安全 |

产品可以维护用户体验和业务意图，但风险等级、医学动作和禁止项必须经过相应专业角色批准。

## 中国大陆场景下应纳入评审的官方要求

以下仅用于产品和技术规划，不构成法律意见；正式上线前应由公司法务、医学与注册团队按实际业务、用户群、数据流和产品声明进行判断。

1. 《生成式人工智能服务管理暂行办法》要求根据服务类型提高生成内容准确性和可靠性，明确服务适用人群、场合和用途，并保护用户输入和使用记录。官方来源：[国家网信办](https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm)。
2. 《个人信息保护法》将医疗健康信息列为敏感个人信息；处理应具有特定目的和充分必要性，并采取严格保护措施。官方来源：[国家网信办](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm?eqid=c1b27c46000007a10000000664659814)。
3. 《互联网诊疗监管细则（试行）》要求互联网诊疗由符合要求的医疗机构和医务人员开展，并明确严禁使用人工智能等自动生成处方；同时对诊疗记录、信息保护和质量安全提出要求。官方来源：[国家卫生健康委](https://www.nhc.gov.cn/yzygj/c100068/202203/2072f0e8988249e59d942e1b2a933916.shtml)。
4. 如果软件的预期用途涉及疾病诊断、治疗决策等医疗目的，可能涉及医疗器械分类与注册问题，应基于具体功能申请或咨询分类界定，不能只靠产品名称或免责声明判断。官方分类服务入口：[国家药监局](https://zwfw.nmpa.gov.cn/web/taskview/11100000MB0341032Y100207202300001)。

对当前项目最直接的产品含义是：

- `history.jsonl` 保存了健康信息和完整 Prompt，不能在真实产品中无期限、无权限地明文保存。
- 将个人睡眠数据发送给第三方模型前，需要完成必要性、告知同意、合同、存储和跨境等实际数据流审查。
- “不诊断疾病”的 Prompt 是必要的，但不足以替代代码拦截、医学审核、日志审计和人工升级。
- “健康管理”和“互联网诊疗”的边界必须由实际预期用途、功能、用户界面和运营流程共同决定。

---

# 第一部分：项目全貌

## 1. 项目要解决什么问题

这个项目围绕一条具体问题建立最小闭环：

> 用户问“我昨晚睡得怎么样？”时，系统读取真实睡眠数据，将昨晚与个人近期基线比较，生成简洁回答，并用预先定义的 Rubric 评测回答质量。

它同时包含两个产品：

1. **Playground**：运行 AI Coach，查看回答和 Debug Trace。
2. **Evaluation**：选择与本次结果语义兼容的 Bench Case，对预期路由、参数、检索、Ground Truth 和 Rubric 进行评分。

## 2. 一次问答的完整链路

```text
用户输入问题和日期
        │
        ▼
app.py（UI 与状态管理）
        │
        ▼
backend/coach.py（流程编排）
        │
        ├── backend/router.py
        │       ├── backend/prompts.py 生成 Router Messages
        │       └── backend/model_adapter.py 调用 DeepSeek
        │
        ├── 判断是否属于睡眠范围
        │
        ├── backend/data_service.py
        │       └── sleep_sessions.csv
        │
        ├── backend/prompts.py 生成 Coach Messages
        │
        └── backend/model_adapter.py 调用 DeepSeek
                │
                ▼
          AI Coach Answer
                │
                ├── app.py 显示
                └── history_service.py 保存
```

## 3. 一次 Evaluation 的完整链路

```text
最新一次 Playground 结果
        │
        ├── 当前日期与 Bench 日期相同？
        ├── module 相同？
        ├── prototype 相同？
        ├── intent 相同？
        └── answerability 相同？
                │
                ▼
backend/evaluator.py
        │
        ├── 加载 sleep_p05_001.json
        ├── 加载 p05_rubrics.json
        ├── 重新计算 Ground Truth
        ├── 计算 Routing Score
        └── 每条 Rubric 调用一次 LLM Judge
                │
                ▼
Routing Score + Response Score + 逐项解释
```

## 4. 目录职责

```text
ai-coach-lab-v0.1/
├── app.py                         Streamlit 入口与页面控制
├── backend/                       业务逻辑和外部服务适配
│   ├── __init__.py                把 backend 标记为 Python 包
│   ├── env.py                     加载 .env
│   ├── model_adapter.py           DeepSeek API 适配层
│   ├── prompts.py                 Router、Coach、Judge Prompt
│   ├── router.py                  意图识别与 JSON 解析
│   ├── data_service.py            睡眠数据与基线计算
│   ├── coach.py                   问答流程编排
│   ├── evaluator.py               路由和回答评分
│   └── history_service.py         JSONL 历史记录
├── bench/
│   └── sleep_p05_001.json         固定测试用例
├── config/
│   ├── p05_rubrics.json           评分规则
│   └── product_decisions.json     尚未最终确认的产品口径
├── data/
│   ├── raw/                       原始数据
│   ├── normalized/                规范化数据和 Ground Truth
│   └── runs/                      实际运行记录
├── scripts/
│   └── run_single_eval.py         命令行评测入口
├── requirements.txt               Python 依赖
├── README.md                      使用说明
└── ARCHITECTURE.md                简要架构图
```

## 5. 项目中的四类数据

| 类型 | 示例 | 含义 |
|---|---|---|
| 用户输入 | `我昨晚睡得怎么样？` | 本次运行的动态输入 |
| 产品数据 | 睡眠时长、HRV、效率 | Coach 可以看到的个人数据 |
| 测试契约 | Bench Case、Expected Routing | 系统预期行为 |
| Evaluator-only | Rubric、Ground Truth | 只供评测使用，不应泄露给 Candidate |

## 6. 必备 Python 语法速查

### 字典与列表

```python
person = {"name": "Alice", "age": 20}
items = ["a", "b", "c"]
```

JSON Object 进入 Python 后通常是 `dict`，JSON Array 通常是 `list`。

### 函数

```python
def add(a, b=1):
    return a + b
```

`b=1` 是默认参数。

### 类与对象

```python
class Model:
    def __init__(self, name):
        self.name = name
```

`self` 类似其他语言中的 `this`。

### 条件、循环与异常

```python
if condition:
    ...

for item in items:
    ...

try:
    risky_operation()
except Exception as exc:
    handle(exc)
```

### 常见真值规则

以下值在条件判断中为假：

```python
False
None
0
""
[]
{}
```

---

# 第二部分：逐课精读

# 第 1 课：`app.py`——UI 入口与状态管理

## 1.1 文件职责

`app.py` 类似 Controller + View：

- 初始化配置和模型。
- 接收用户输入。
- 调用后端函数。
- 保存当前状态和历史。
- 控制是否允许运行 Evaluation。
- 展示回答、Trace、分数和 Rubric 解释。

它不负责计算睡眠基线，也不直接实现模型调用。

## 1.2 Streamlit 的重运行模型

Streamlit 的关键规则是：用户操作控件后，Python 文件通常会从头到尾重新执行。

```text
用户点击按钮
→ app.py 重新运行
→ 当前控件值重新读取
→ 按钮在该轮返回 True
→ 业务函数执行
→ 页面重新绘制
```

因此普通变量不能可靠保存跨重绘状态，需要：

```python
st.session_state
```

当前项目保存：

```python
st.session_state["last"]     # 最近一次结果
st.session_state["history"]  # 当前会话中的历史列表
```

## 1.3 初始化顺序

```python
load_dotenv_if_present()
case = load_case()
model = OpenAICompatibleModel()
st.set_page_config(...)
```

必须先加载 `.env`，再创建模型；否则构造函数读取不到环境变量。

`ROOT = Path(__file__).resolve().parent` 得到项目根目录，但当前版本没有实际使用，是可清理变量。

## 1.4 恢复历史

```python
if "history" not in st.session_state:
    st.session_state["history"] = load_runs()
```

仅在当前 Session 第一次执行时从磁盘读取。

```python
if "last" not in st.session_state and st.session_state["history"]:
    st.session_state["last"] = st.session_state["history"][0]["result"]
```

历史按从新到旧排列，因此 `[0]` 是最近一次。

## 1.5 Playground

```python
query = st.text_input("用户问题", value=case["model_input"]["query"])
date = st.text_input("Query Context Date", value=case["model_input"]["query_context_date"])
```

输入框默认值来自 Bench Case，但用户可以修改。

点击发送后：

```python
result = run_coach(query, date, model)
st.session_state["last"] = result
record = append_run(result)
st.session_state["history"].insert(0, record)
```

这里同时写入两层存储：

- `session_state`：页面会话内立即可用。
- `history.jsonl`：刷新和重启后仍存在。

## 1.6 为什么回答不会在切换标签后消失

显示逻辑位于按钮之外：

```python
if "last" in st.session_state:
    st.write(st.session_state["last"]["answer"])
```

如果只在 `if st.button(...)` 内显示，下一次重绘时按钮为假，正文就会消失。

## 1.7 历史渲染

```python
for record in st.session_state["history"]:
    saved = record["result"]
```

`dict.get(key, default)` 用于兼容旧记录中可能缺失的字段：

```python
saved.get("query", "未知问题")
```

`json.dumps(..., ensure_ascii=False, indent=2)` 用于生成可下载的中文 JSON。

## 1.8 Evaluation 兼容判断

```python
compatible = (
    current_date == case["model_input"]["query_context_date"]
    and all(actual.get(k) == expected.get(k) for k in expected)
)
```

这里不再逐字比较问题，而是比较：

- 数据日期。
- `module`。
- `prototype`。
- `intent`。
- `answerability`。

`all(...)` 只有在生成器中的所有布尔值都为真时才返回真。

## 1.9 当前局限

- 日期使用自由文本，缺少格式验证。
- 页面只能评测最近一次回答。
- Evaluation 结果尚未写入历史。
- `app.py` 接近 100 行，可拆为 `render_playground()` 和 `render_evaluation()`。
- `except Exception` 适合 Demo，但开发模式下最好保留完整堆栈。

---

# 第 2 课：`backend/env.py`——配置加载

## 2.1 文件职责

把项目根目录中的 `.env` 文本转换为当前 Python 进程的环境变量。

```text
.env → env.py → os.environ → model_adapter.py
```

## 2.2 定位项目根目录

```python
p = Path(__file__).resolve().parents[1] / ".env"
```

当 `__file__` 是 `backend/env.py` 时：

```text
parents[0] = backend
parents[1] = 项目根目录
```

`Path` 对象中的 `/` 表示拼接路径，不是除法。

## 2.3 逐行解析

```python
for line in p.read_text(encoding="utf-8").splitlines():
```

处理步骤：

1. `strip()` 去掉两端空白。
2. 忽略空行。
3. 忽略 `#` 开头的注释。
4. 忽略不含 `=` 的行。
5. `split("=", 1)` 只按第一个等号切分。

只切分一次很重要，因为值本身可能含有等号。

## 2.4 `setdefault` 的优先级

```python
os.environ.setdefault(k.strip(), v.strip())
```

只有环境变量尚不存在时才写入，所以优先级是：

```text
进程已有环境变量 > .env
```

这也解释了修改 `.env` 后为什么通常需要重启 Streamlit：旧进程里即使已有空字符串，`setdefault` 也不会覆盖。

## 2.5 安全与限制

- 不要打印完整 `os.environ`，其中可能包含 API Key。
- 当前解析器不完整支持引号、`export` 和行尾注释。
- 它不验证 Key 是否有效，只负责加载。

---

# 第 3 课：`backend/model_adapter.py`——模型适配层

## 3.1 设计目标

上层统一调用：

```python
model.chat(messages, ...)
```

而无需关心 SDK 初始化、Base URL、JSON Mode、思考模式和空响应重试。

这是一种 Adapter Pattern。

## 3.2 类与构造函数

```python
class OpenAICompatibleModel:
    def __init__(self):
        self.api_key = os.getenv(...)
```

`self` 表示当前对象。`__init__` 在创建对象时自动执行。

`OpenAICompatible` 指 DeepSeek 使用兼容 OpenAI Chat Completions 的协议，不表示请求发往 OpenAI。实际服务由 `base_url` 决定。

## 3.3 配置状态属性

```python
@property
def configured(self):
    return bool(self.api_key and self.base_url and self.model)
```

`@property` 让调用方使用 `model.configured`，而不是 `model.configured()`。

它只检查非空，不检查 Key 是否真实有效。

## 3.4 `chat()` 参数

| 参数 | 作用 |
|---|---|
| `messages` | 发给模型的有序消息列表 |
| `temperature` | 输出随机性 |
| `max_tokens` | 最大输出 Token |
| `json_mode` | 是否启用严格 JSON Output |
| `retries` | 空内容后的重试次数 |
| `thinking` | 是否启用 DeepSeek 思考模式 |

## 3.5 请求结构

```python
request = {
    "model": self.model,
    "messages": messages,
    "temperature": temperature,
    "max_tokens": max_tokens,
    "extra_body": {
        "thinking": {"type": "enabled" if thinking else "disabled"}
    },
}
```

`"enabled" if thinking else "disabled"` 是条件表达式。

当 `json_mode=True` 时增加：

```python
request["response_format"] = {"type": "json_object"}
```

## 3.6 `messages` 的标准结构

```python
messages = [
    {"role": "system", "content": "稳定规则"},
    {"role": "user", "content": "本次问题和数据"},
]
```

外层格式由 Chat Completions 协议决定，具体内容由 `prompts.py` 决定。

常见角色：

- `system`：身份、规则、输出约束。
- `user`：本次问题和动态数据。
- `assistant`：历史模型回答，多轮对话时使用。

## 3.7 字典解包

```python
client.chat.completions.create(**request)
```

`**request` 把字典展开为命名参数。

## 3.8 响应结构

```python
resp.choices[0].message.content
```

含义：取第一个候选结果中的 Assistant Message，再取其最终正文。

```python
content = ... or ""
```

把 `None` 转成空字符串，避免调用 `.strip()` 时报错。

## 3.9 重试逻辑

```python
for attempt in range(retries + 1):
```

`retries=2` 表示最多请求三次：首次一次，加两次重试。

当前只重试空正文，不重试网络超时、429 或 500，也没有指数退避，这是后续可增强点。

---

# 第 4 课：`backend/prompts.py`——Prompt 与 Message 工厂

## 4.1 为什么集中管理 Prompt

Prompt 属于产品逻辑和模型行为契约。集中管理可以：

- 避免散落在业务代码中。
- 方便版本对比。
- 让 Router、Candidate、Judge 的信息边界清晰。
- 支持后续 Prompt A/B Test。

## 4.2 Router System Prompt

它规定输出四个字段：

```text
module
prototype
intent
answerability
```

睡眠综合问题应输出：

```json
{
  "module": "sleep",
  "prototype": "P05",
  "intent": "multi_metric_night_summary",
  "answerability": "answer"
}
```

非睡眠问题应输出：

```json
{
  "module": "unsupported",
  "prototype": "none",
  "intent": "out_of_scope",
  "answerability": "cannot_answer"
}
```

当前路由覆盖八个基础原型，仍然只是睡眠场景Demo，不是通用健康意图系统。

## 4.3 Coach System Prompt

核心要求包括：

- 先给整体判断。
- 与个人基线比较。
- 只选 2–4 个重要事实。
- 不把相关性写成因果。
- 不编造数据。
- 不做单晚医学诊断。

这些规则与 Rubric 大体呼应，但 Candidate 看不到具体 Rubric。

## 4.4 Judge System Prompt

Judge 每次只判断一条 Rubric，输出：

```json
{
  "criteria_met": true,
  "explanation": "原因"
}
```

负向 Rubric 的语义尤其重要：只有坏行为真的出现时，`criteria_met` 才为真，此时负分会被计入。

## 4.5 三种 Message 工厂

`router_messages()` 把问题和上下文序列化成 JSON 字符串。

`coach_messages()` 把用户问题和检索到的个人数据放入同一条 User Message。

`judge_messages()` 提供问题、Ground Truth、候选回答和单条 Rubric。

`json.dumps(..., ensure_ascii=False)` 保留中文；`indent=2` 主要提升可读性。

---

# 第 5 课：`backend/router.py`——意图识别与结构化解析

## 5.1 输入输出

输入：

```python
route(query, context, model)
```

输出：

```python
{
    "parsed": {...},
    "raw": "模型原始 JSON 文本"
}
```

保留 `raw` 是为了 Debug 和审计，`parsed` 用于程序判断。

## 5.2 调用模型

Router 使用：

```python
temperature=0.0
max_tokens=500
json_mode=True
retries=2
thinking=False
```

因为分类任务追求稳定而非创造性。

## 5.3 清理 Markdown Code Fence

```python
cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
```

即使要求只输出 JSON，模型仍可能包裹：

````text
```json
{"module":"sleep"}
```
````

正则表达式删除首尾围栏。

## 5.4 JSON 解析与异常链

```python
try:
    parsed = json.loads(cleaned)
except json.JSONDecodeError as exc:
    raise RuntimeError(...) from exc
```

`from exc` 保留原始异常作为原因，便于追踪。

随后检查：

```python
isinstance(parsed, dict)
```

确保顶层结构是 Object，而不是 Array 或字符串。

## 5.5 当前缺口

这里只验证“是字典”，尚未验证：

- 四个字段是否齐全。
- 字段值是否属于允许枚举。
- 是否包含未知字段。

后续可用 Pydantic 或 JSON Schema 做严格校验。

---

# 第 6 课：`backend/data_service.py`——睡眠数据与个人基线

## 6.1 文件职责

从规范化 CSV 中找出目标主睡眠，并计算此前最近 N 次主睡眠的平均值。

## 6.2 数据路径

```python
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "normalized" / "sleep_sessions.csv"
```

相对源文件定位使程序不依赖当前 PowerShell 工作目录。

## 6.3 函数签名与类型标注

```python
def get_night_and_baseline(query_context_date: str, baseline_n: int = 7):
```

`query_context_date: str` 是类型提示，运行时通常不会自动强制。

`baseline_n=7` 是默认参数，因此也可调用：

```python
get_night_and_baseline("2026-05-07", baseline_n=14)
```

## 6.4 读取和清洗日期

```python
df = pd.read_csv(DATA)
df["day_dt"] = pd.to_datetime(df["day"], errors="coerce")
```

`errors="coerce"` 把无法解析的日期变成 `NaT`，而不是直接报错。

## 6.5 筛选主睡眠

```python
long_sleep = df[df["type"].astype(str).str.lower().eq("long_sleep")].copy()
```

链式含义：

1. 转成字符串。
2. 转小写。
3. 判断是否等于 `long_sleep`。
4. 用布尔掩码筛选 DataFrame。
5. `.copy()` 避免对切片修改时产生歧义。

然后删除无效日期并排序：

```python
dropna(...).sort_values("day_dt")
```

## 6.6 找目标夜晚

```python
rows = long_sleep[long_sleep["day_dt"] == target]
```

如果为空，返回可序列化的业务结果：

```python
{"available": False, "reason": "没有找到对应主睡眠数据"}
```

这不是异常，而是正常的“数据不可用”分支。

## 6.7 选择目标行与基线窗口

```python
row = rows.iloc[-1]
```

若同一天有多条记录，取最后一条。

```python
prev = long_sleep[long_sleep["day_dt"] < target].tail(baseline_n)
```

取目标日期以前最近 N 条主睡眠，不包含目标夜晚。

## 6.8 指标转换

程序遍历九个指标，使用：

```python
pd.to_numeric(..., errors="coerce")
```

无效值转为 `NaN`。

输出时：

```python
None if pd.isna(v) else float(v)
```

因为 `None` 能被 JSON 编码为 `null`，而 `NaN` 不是严格 JSON 的标准值。

基线使用：

```python
vals.mean()
```

计算最近有效记录的算术平均。

## 6.9 当前产品口径

- “昨晚”暂定义为 `query_context_date` 当天醒来的 `long_sleep`。
- 基线是此前最近 7 次有效 `long_sleep`，不一定等于连续七个自然日。
- 暂未做异常日剔除、最少有效天数和时区校正。

---

# 第 7 课：`backend/coach.py`——业务流程编排器

## 7.1 为什么需要编排层

`coach.py` 不实现每个底层能力，而是决定执行顺序和分支：

```text
Route → Scope Gate → Retrieve → Build Prompt → Generate → Return Trace
```

## 7.2 Trace

```python
trace = {}
```

Trace 记录中间步骤，供调试、研究和历史审计：

```text
routing
retrieval
generation_messages
raw_generation
```

## 7.3 路由与范围拦截

```python
parsed = routing["parsed"]
if parsed.get("module") != "sleep" or parsed.get("answerability") != "answer":
```

任何一个条件不满足就跳过数据查询，返回固定的能力边界说明。

例如“蜘蛛侠好看吗”应得到：

```json
{
  "module": "unsupported",
  "answerability": "cannot_answer"
}
```

此时 Trace 明确记录：

```python
{"skipped": True, "reason": "out_of_scope"}
```

## 7.4 数据不可用分支

如果日期没有对应主睡眠，系统不让 LLM 猜测，而是直接返回确定性文本。

这是比“让模型自由处理缺失数据”更安全的设计。

## 7.5 生成回答

```python
messages = coach_messages(query, retrieved)
answer = model.chat(messages, temperature=0.3, max_tokens=1200)
```

Candidate 使用自然语言模式，默认关闭思考模式和 JSON Mode。

## 7.6 返回契约

三个主要分支都返回相似结构：

```python
{
    "query": ...,
    "query_context_date": ...,
    "answer": ...,
    "trace": ...,
}
```

稳定的返回结构让 UI 和历史服务无需知道具体走了哪个分支。

---

# 第 8 课：`bench/sleep_p05_001.json`——测试用例契约

## 8.1 Bench Case 不是聊天记录

Bench Case 描述的是一个可重复测试场景：

- 给模型什么输入。
- Router 应输出什么。
- 应检索哪些数据。
- 使用什么 Rubric。
- 哪些信息只能给 Evaluator。

## 8.2 主要字段

### `case_id`

```json
"case_id": "SLEEP_P05_001"
```

稳定标识符，适合统计、版本管理和 Bad Case 追踪。

### `model_input`

代表测试时给系统的输入，包括问题、上下文日期和页面上下文。

### `expected_routing`

定义正确路由，用于计算 Routing Score 和判断语义是否兼容。

### `expected_retrieval`

声明期望字段和基线口径。当前 `evaluator.py` 已将它与本次 Trace 中的实际 Retrieval 对比，输出 Retrieval Score。

### `evaluator_only`

声明 Ground Truth 文件和参考答案说明。Candidate 不应看到这些内容。

**重要：当前 `evaluator.py` 没有读取 `ground_truth_file`，而是调用 `get_night_and_baseline()` 重新计算 Ground Truth。**

### `rubric_files`

声明一个或多个 Rubric 路径。`load_rubrics(case)` 会按当前 Case 动态加载，P01和P05因此可以使用不同标准。

### `product_decision_refs`

把 Case 与尚未最终确认的产品口径关联起来，当前代码没有自动展开这些引用。

## 8.3 JSON 基础

JSON 支持：

- Object `{}`
- Array `[]`
- String
- Number
- Boolean
- `null`

JSON 不支持注释、尾逗号和 Python 的 `None`。

---

# 第 9 课：`config/p05_rubrics.json`——评分规则

## 9.1 Rubric 结构

每条规则包含：

```json
{
  "id": "R01",
  "criterion": "判断标准",
  "points": 4,
  "tags": ["summary", "ux"]
}
```

## 9.2 正向与负向规则

正分规则：满足时加分。

```text
R01 +4
R02 +6
R03 +4
R04 +5
R05 +6
```

正向总分：

```text
4 + 6 + 4 + 5 + 6 = 25
```

负向规则：坏行为出现时扣分。

```text
R06 -10：单晚数据诊断疾病
R07 -3：无关健康科普过多
```

因此 Response Score 可能低于 0，但不会因为负向规则未触发而自动加分。

## 9.3 为什么一条 Rubric 调用一次 Judge

优点：

- 判断目标单一。
- 解释容易追踪。
- 单条失败容易重跑。

缺点：

- API 调用次数多。
- 成本和延迟随 Rubric 数量线性增长。
- 各次判断之间可能不一致。

---

# 第 10 课：`config/product_decisions.json`——产品口径登记

## 10.1 为什么它不应藏在代码里

“昨晚怎样定义”“基线取几天”“是否使用医学阈值”不是纯技术事实，而是产品、算法和医学共同决定的口径。

将其登记为配置，有利于：

- 识别临时假设。
- 记录待评审事项。
- 避免团队误把 Demo 规则当成最终定义。

## 10.2 `provisional`

三个决策都标记为：

```json
"status": "provisional"
```

表示目前可用于 Demo，但尚未正式确认。

## 10.3 当前代码关系

这些决策并不是运行时自动读取的规则引擎。实际规则仍写在：

- `data_service.py`：主睡眠和七次基线。
- `prompts.py`：整体判断交给 LLM。

所以它当前主要承担文档和治理作用。

---

# 第 11 课：`backend/evaluator.py`——评测执行器

## 11.1 加载 Case 和 Rubric

```python
json.loads(path.read_text(encoding="utf-8"))
```

先读取文本，再把 JSON 字符串解析为 Python 字典或列表。

## 11.2 Routing Score

评分字段固定为：

```python
["module", "prototype", "intent", "answerability"]
```

字典推导式生成详情：

```python
details = {
    f: {
        "expected": expected.get(f),
        "actual": pred.get(f),
        "ok": pred.get(f) == expected.get(f)
    }
    for f in fields
}
```

得分是正确字段数除以字段总数：

```python
sum(v["ok"] for v in details.values()) / len(fields)
```

Python 中 `True` 可按 `1` 求和，`False` 按 `0`。

## 11.3 Ground Truth

```python
gt = get_night_and_baseline(case["model_input"]["query_context_date"])
```

当前评测实时从 CSV 重新计算，没有读取 `demo_ground_truth.json`。这能避免静态文件过期，但也意味着 Bench 中声明的 Ground Truth 路径尚未真正成为数据源。

## 11.4 Rubric 循环

```python
for rubric in load_rubrics(case):
```

Judge API 请求次数等于当前 Case 加载的 Rubric 条数；若出现空响应，单条最多请求三次。

每次都使用严格 JSON Mode，并解析：

```json
{
  "criteria_met": true,
  "explanation": "..."
}
```

当前仅使用 `bool(parsed.get("criteria_met"))`，没有严格验证该字段原本是否确实是 JSON Boolean。例如字符串 `"false"` 在 Python 中是真值，这是潜在风险，适合以后用 Schema 解决。

## 11.5 Response Score

```python
pos = sum(所有正向 Rubric 的 points)
achieved = sum(所有 criteria_met 为真的 points)
response_score = achieved / pos
```

假设 R01、R02、R05 满足，且 R06 坏行为出现：

```text
achieved = 4 + 6 + 6 - 10 = 6
response_score = 6 / 25 = 24%
```

## 11.6 Judge Bias

当前 Candidate 和 Judge 可以使用同一个模型。同一模型可能偏好与自身相似的表达方式，导致评分偏高或形成系统性盲点。

后续可采用：

- 独立 Judge 模型。
- 多 Judge 投票。
- 人工抽检。
- 规则评分与 LLM 评分混合。

---

# 第 12 课：`data/normalized/demo_ground_truth.json`——静态真值快照

## 12.1 内容

它保存目标夜晚和七次基线的数值快照，包括：

- 总睡眠。
- 深睡。
- REM。
- 清醒时间。
- 效率。
- 心率。
- HRV。
- 呼吸率。

## 12.2 时间单位

例如：

```json
"total_sleep_duration": 25740.0
```

从项目回答和数据量级看，这些 duration 字段实际按秒处理：

```text
25740 秒 ÷ 3600 ≈ 7.15 小时
```

但当前数据契约没有显式写单位，这是值得补充的地方。

## 12.3 当前未直接使用

Bench 引用了这个文件，但 `run_eval()` 实际重新计算 Ground Truth。它目前主要用于：

- 人工核对。
- 固定快照。
- 防止数据计算变化时无法追溯旧预期。

---

# 第 13 课：`backend/history_service.py`——持久化运行记录

## 13.1 JSONL 与 JSON 的区别

普通 JSON 文件通常是一个完整数组：

```json
[{"a":1},{"a":2}]
```

JSONL 是每行一个独立 JSON Object：

```text
{"a":1}
{"a":2}
```

优点是可以直接追加新行，不必读取并重写整个数组。

## 13.2 记录结构

```python
record = {
    "run_id": str(uuid4()),
    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "result": result,
}
```

- `uuid4()` 生成近似唯一 ID。
- `astimezone()` 加入本地时区信息。
- ISO 时间便于排序和跨系统解析。

## 13.3 创建目录与追加写入

```python
HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
```

- `parents=True`：父目录不存在时一并创建。
- `exist_ok=True`：目录已存在时不报错。

```python
with HISTORY_FILE.open("a", encoding="utf-8") as f:
```

`"a"` 是 append 模式；`with` 确保结束后文件自动关闭。

## 13.4 加载历史

程序逐行解析，跳过空行和损坏行，最后：

```python
list(reversed(records[-limit:]))
```

先取最后 `limit` 条，再反转为从新到旧。

## 13.5 当前局限

- 没有文件锁，并发写入可能冲突。
- 损坏行被静默跳过，没有告警。
- 文件长期增长，没有归档策略。
- 保存了完整 Prompt 和个人数据，应考虑隐私、脱敏和保留周期。

---

# 第 14 课：`scripts/run_single_eval.py`——命令行入口

## 14.1 与网页入口的区别

它没有 UI，按固定 Case 自动执行：

```text
加载配置
→ 创建模型
→ 加载 Case
→ 生成回答
→ 运行全部 Rubric
→ 打印结果
```

适合：

- 自动化测试。
- CI。
- 批量 Eval 的原型。
- 不启动浏览器时调试。

## 14.2 推荐运行方式

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_single_eval
```

使用 `-m` 能让项目根目录保持在模块搜索路径中，避免找不到 `backend`。

## 14.3 当前输出局限

它直接打印 Python 字典，不够适合长期保存。后续可以：

- 输出格式化 JSON。
- 保存到带时间戳的结果文件。
- 返回非零退出码表示阈值失败。
- 支持指定 Case 路径和模型。

---

# 第 15 课：辅助文件

## 15.1 `backend/__init__.py`

当前为空。它表示 `backend` 是 Python 包，并支持：

```python
from backend.coach import run_coach
```

包内部使用：

```python
from .router import route
```

开头的 `.` 表示从当前包相对导入。

## 15.2 `requirements.txt`

```text
streamlit>=1.36
pandas>=2.0
openai>=1.0
```

`>=` 允许安装更高版本，方便但可重复性较弱。生产项目通常会锁定经过验证的版本或使用 lock file。

## 15.3 `README.md`

面向使用者，解释项目目标、启动命令和已知限制。

当前 README 还未完全反映后续新增的历史记录、范围拦截和语义兼容逻辑，后续应同步更新。

## 15.4 `ARCHITECTURE.md`

提供高层链路，强调 Candidate 不应看到 Evaluator-only 信息。这是防止评测泄漏的关键边界。

## 15.5 原始与规范化 CSV

`data/raw/sleepmodel.csv` 是原始输入，`data/normalized/sleep_sessions.csv` 是业务代码实际读取的数据。

当前两者行数相同，但架构上仍应保持：

```text
raw：可追溯，不轻易改动
normalized：字段稳定，供程序消费
```

---

# 第三部分：关键数据结构

## 16. Router 输出

```python
{
    "module": "sleep",
    "prototype": "P05",
    "intent": "multi_metric_night_summary",
    "answerability": "answer",
}
```

## 17. Retrieval 输出

```python
{
    "available": True,
    "query_context_date": "2026-05-07",
    "source_session_id": "...",
    "bedtime_start": "...",
    "bedtime_end": "...",
    "night": {...},
    "baseline_7d": {...},
}
```

## 18. Coach 输出

```python
{
    "query": "我昨晚睡得怎么样？",
    "query_context_date": "2026-05-07",
    "answer": "昨晚整体……",
    "trace": {
        "routing": {...},
        "retrieval": {...},
        "generation_messages": [...],
        "raw_generation": "...",
    },
}
```

## 19. Eval 输出

```python
{
    "routing_score": {...},
    "response_score": 0.8,
    "rubric_results": [...],
    "ground_truth": {...},
    "limitation": "...",
}
```

---

# 第四部分：运行与调试

## 20. 启动网页

```powershell
cd D:\download\ai-coach-lab-v0.1
.\.venv\Scripts\python.exe -m streamlit run app.py
```

访问：

```text
http://localhost:8501
```

## 21. 语法检查

```powershell
.\.venv\Scripts\python.exe -m compileall -q app.py backend scripts
```

它只能检查语法和导入阶段的部分问题，不能证明真实 API 和数据流程正确。

## 22. 观察 Debug Trace

推荐按顺序查看：

1. `routing.raw`：模型原始路由文本。
2. `routing.parsed`：程序解析后的路由。
3. `retrieval`：目标夜晚和基线。
4. `generation_messages`：最终送给 Candidate 的上下文。
5. `raw_generation`：模型原始回答。

## 23. 常见错误定位

### `Expecting value: line 1 column 1`

通常表示把空字符串或非 JSON 文本传给 `json.loads()`。当前项目已通过 JSON Mode 和空响应重试缓解。

### 找不到 `backend`

从错误目录直接运行脚本可能导致模块搜索路径不正确。使用项目根目录和 `python -m ...`。

### 修改 `.env` 未生效

由于 `os.environ.setdefault()` 不覆盖已有值，需要重启 Python/Streamlit 进程。

### Evaluation 被禁用

检查日期和四个路由字段是否与 Bench Case 一致；原始问题文字可以不同。

---

# 第五部分：架构评估与演进

## 24. 当前架构的优点

- UI、流程、数据、Prompt、模型和评测职责基本分离。
- Candidate 与 Evaluator-only 信息存在明确边界。
- Trace 便于研究和复现。
- 真实数据查询是确定性 Python 逻辑，不交给 LLM 编造。
- Router 和 Judge 使用结构化输出。
- Out-of-scope 请求在数据查询前被拦截。
- 历史记录可跨重启保留。

## 25. 当前最重要的技术债

1. Bench 中的 `ground_truth_file` 和 `product_decision_refs` 尚未被动态执行。
2. Retrieval Score 当前检查字段覆盖与基线存在性，尚未验证来源窗口和具体数值。
3. Router 和 Judge 输出缺少完整的严格 Schema 校验。
4. Candidate 与 Judge 可能是同一模型。
5. API 调用缺少超时、网络错误重试、退避和 Token 统计。
6. 历史记录包含个人数据，缺少脱敏和生命周期策略。
7. 当前八个原型都只有基础Case，长尾表达、组合意图和跨轮对话覆盖仍有限。
8. Evaluation 结果尚未持久化。
9. 依赖版本没有完全锁定。
10. 目前有核心离线测试，但仍缺少完整UI与真实API回归测试套件。

## 26. 推荐演进顺序

### 阶段 A：让当前 Case 更可靠

- 为 Router/Judge 建立 Pydantic Schema。
- 对 Expected Retrieval 自动评分。
- 将 Evaluation 结果写入历史。
- 增加 API Usage、Latency 和 Retry Trace。

### 阶段 B：支持多个 Case

- Case Loader 接受文件路径或 Case ID。
- Rubric 路径从 Case 动态读取。
- Ground Truth 按 Case 配置加载或计算。
- 页面支持从 Bench 列表选择 Case。

### 阶段 C：形成 Eval 平台

- 批量运行 Case。
- 按模型和 Prompt 版本对比。
- Bad Case 分类。
- 人工复核工作流。
- 统计置信区间和回归趋势。

---

# 第六部分：学习练习

## 27. 基础练习

1. 解释 `dict.get()` 与 `dict[]` 的区别。
2. 解释 `retries=2` 为什么最多请求三次。
3. 解释 `system` 和 `user` Message 的职责。
4. 解释 `session_state` 与 `history.jsonl` 的区别。
5. 解释为什么睡眠数据查询由 Python 完成而不是由 LLM 完成。

## 28. 中级练习

1. 给 `data_service.py` 增加实际使用的基线记录数量。
2. 把日期文本框改为 `st.date_input()`。
3. 给 Router 输出增加必填字段检查。
4. 把 Evaluation 结果保存进历史。
5. 让页面可以选择一条旧记录重新评测。

## 29. 高级练习

1. 实现一个新的单指标睡眠时长 Case。
2. 让 `rubric_file` 真正驱动 Rubric 加载。
3. 增加独立 Judge 模型配置。
4. 建立批量 Eval CLI。
5. 为路由、数据服务和评分函数编写自动测试。

---

# 结语

理解本项目最重要的不是记住 Python 语法，而是抓住三条边界：

1. **确定性逻辑与概率性模型的边界**：数据查询和评分计算用 Python，语言理解和解释用 LLM。
2. **Candidate 与 Evaluator 的信息边界**：Rubric 和 Ground Truth 不泄露给 Candidate。
3. **运行输入与测试契约的边界**：Playground 可以自由提问，Evaluation 只能对语义兼容的 Bench Case 评分。

沿着这三条边界继续扩展，项目才能从一个可运行 Demo 演进成可靠的 AI Coach Eval Lab。

---

# 第七部分：Workflow Studio（2026-08-22新增）

## 30. 为什么不能只显示一个Debug JSON

旧版 `trace` 虽然保存了Routing、Policy、Retrieval和Messages，但字段不统一，也无法表达某节点是否执行、为什么跳过、耗时多少、对应哪些源码。Workflow Studio增加了统一Node Trace，让一次AI回答成为可以复盘的产品执行链路，而不是一段难以阅读的日志。

## 31. Node Trace结构

节点注册表在 `config/workflow_modules.json`，运行记录器在 `backend/workflow_trace.py`。每个节点统一拥有 `status`、`input`、`output`、`duration_ms`、`files` 和 `meta`。`backend/coach.py` 在实际调用安全预检、Router、Policy、Retrieval、Prompt和模型时写入节点，因此页面显示的不是预设动画。

## 32. 三栏工作台

- 左侧模块目录自动覆盖项目中的Python和JSON文件。
- 中间显示12个回答节点及成功、拦截、跳过、失败状态。
- 右侧显示对话，并可切换节点概览、输入、输出和源码。
- Evaluation拥有独立的5节点Trace。
- Run History可以回放新旧两种记录；旧记录由兼容转换器生成可视化节点。

## 33. 当前产品边界

第一版只读、不改线、不在线编辑Prompt或Python，每次完整运行后回看。这一边界让工具先解决团队调试、学习和Bad Case复盘问题，同时为后续版本比较、成本统计、节点失败率和团队协作保留统一数据结构。
