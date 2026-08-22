# AI Coach 项目简历量化与7天回归计划

## 使用说明

本文将项目指标分成三类：

1. **当前已经完成、可以立即写进简历的真实数字**；
2. **未来7天通过批量回归可以真实测出的提升数字**；
3. **不能提前填写、必须等待实际结果的占位符**。

核心原则：每个简历数字都应能通过代码、Case文件、运行记录或评测结果证明。不要为了让简历看起来更强而提前虚构Routing Accuracy、Bad Case数量或团队使用效果。

简历表达遵循：

```text
行动 + 问题/场景 + 方法 + 量化结果 + 产品价值
```

---

# 一、当前已经可以写的真实数字

当前项目可验证的结构性指标如下：

| 能力 | 当前已完成 |
|---|---:|
| 已注册回答原型 | 8类：P01/P02/P05/P07/P11/P12/P14/P25 |
| Bench Case | 11条 |
| 已有Case覆盖原型 | 7类 |
| Rubric文件 | 7组 |
| 正负向Rubric规则 | 34项 |
| P07睡眠知识词条 | 11个 |
| 回答Workflow节点 | 12个 |
| Evaluation节点 | 5个 |
| 自动化测试 | 14项 |
| 可观测内容 | 节点输入、输出、耗时、Prompt、Token、源码、跳过原因 |
| 历史能力 | Run ID及全链路Trace持久化 |

这些数字已经存在于当前项目中，可以被面试官追问和现场验证。

---

# 二、今天提交简历可以直接使用的版本

## 项目名称

**AI Coach大健康场景工作流与评测平台｜AI产品经理 / 独立项目负责人**

## 推荐简历描述

- 围绕睡眠报告与健康指标解读场景，规划AI Coach“数据查询—个性化解读—趋势判断—健康科普—风险分流”产品链路，注册P01/P02/P05/P07/P11/P12/P14/P25等 **8类回答原型**，基于DeepSeek API、Python与Streamlit完成可运行MVP。

- 独立设计“安全预检—意图路由—Answerability判断—真实数据检索—个人基线计算—Prompt组装—模型生成—历史追踪”的端到端Workflow，将运行过程拆解为 **12个可观测回答节点及5个Evaluation节点**，支持查看节点级输入输出、耗时、Token、Prompt、源码与跳过原因。

- 搭建AI回答评测框架，沉淀 **11条Bench Case、7组Rubric文件及34项正负向评分标准**，覆盖Routing、参数抽取、数据检索、个性化洞察、不确定性、表达质量与医疗安全，并通过LLM-as-Judge输出逐项评分和Bad Case解释。

- 建立睡眠指标受控知识库，覆盖REM、深睡、睡眠效率、HRV等 **11个核心词条**，采用“结构化知识检索+LLM语言表达”方式限制模型自由发挥，沉淀定义、个人趋势解读、设备测量边界与禁止结论。

- 建立问题、路由、Policy、数据检索、生成Messages和模型输出的全链路Debug Trace与Run History，并通过 **14项自动化测试**验证核心路由、P07检索、安全拦截、Evaluation及敏感字段脱敏能力。

这一版没有虚构准确率提升，但已经具备足够的可验证量化信息。

---

# 三、未来7天建议跑出的核心量化指标

七天内最值得完成的不是继续堆功能，而是建立一套50条左右的回归集，完成一次完整的产品迭代闭环：

```text
建立基线
→ 分类Bad Case
→ 修改规则/Prompt
→ 再次回归
→ 形成前后对比
```

## 3.1 七天建议目标

| 指标 | 当前 | 7天建议产出 |
|---|---:|---:|
| Bench Case | 11条 | 50条 |
| 覆盖原型 | 7类 | 8类原型+3类拒答/升级任务 |
| 问题表达 | 以标准表达为主 | 每个意图包含标准、口语、模糊、近义表达 |
| Bad Case分类 | 尚未形成统计 | 6—7类 |
| Routing Accuracy | 尚未批量计算 | 跑出Baseline和优化后结果 |
| Parameter Accuracy | 尚未批量计算 | 单独计算metric/term/window参数 |
| Retrieval Accuracy | 已有评分函数 | 跑出50条整体结果 |
| End-to-End Pass Rate | 尚未统计 | Routing+Retrieval+Response综合通过率 |
| 安全Case | 1条P25 | 8—10条高风险/诊断/用药Case |
| P07词条 | 11个 | 20—25个 |
| 自动化测试 | 14项 | 25—30项 |
| 团队试用 | 尚未统计 | 3—5人、累计30—50次Run |
| 人工复核 | 尚未统计 | 至少20条回答双人复核 |

## 3.2 50条Case建议分布

| 场景 | 数量 |
|---|---:|
| P01非时长单指标查询 | 5 |
| P02时间点与时长 | 8 |
| P05多指标汇总 | 5 |
| P07指标概念解释 | 8 |
| P11周期趋势比较 | 5 |
| P12个人基线偏离 | 5 |
| P14睡眠综合分析 | 5 |
| P25高风险分流 | 5 |
| 非健康/诊断/用药拒答 | 4 |
| 合计 | 50 |

每个原型需要同时覆盖：

- 标准表达；
- 口语表达；
- 同义改写；
- 模糊表达；
- 边界表达；
- 容易与其他Prototype混淆的表达。

---

# 四、评测指标的统一定义

## 4.1 Routing Exact Match Accuracy

建议使用Case级严格准确率，不使用多个字段的平均正确率冒充整体准确率。

```text
Routing Exact Match Accuracy
= Task、Prototype、Intent、Answerability、Parameters全部正确的Case数
÷ 全部Case数
```

示例：

```text
第一次：39/50 = 78%
优化后：46/50 = 92%
```

简历写法：

> 通过Bad Case复盘优化Router Prompt、原型边界与参数校验，使50条回归集的Routing Exact Match Accuracy由78%提升至92%，提升14个百分点。

注意：78%和92%只是写法示例，不是当前项目真实结果，不能提前使用。

提升幅度应写“提升14个百分点”，而不是“提升14%”。

## 4.2 Parameter Accuracy

单独判断参数抽取是否正确：

```text
我昨晚清醒了多久？
→ metric = awake_time

我几点醒来的？
→ metric = bedtime_end
```

计算公式：

```text
Parameter Accuracy
= metric、term、window等参数正确的Case数
÷ 需要抽取参数的Case数
```

这个指标可以直接反映“清醒时间”等歧义问题是否得到改善。

## 4.3 Retrieval Accuracy

```text
Retrieval Accuracy
= 指标、时间范围、目标记录和数值均正确的Case数
÷ 可回答数据Case数
```

至少检查：

- 是否查询了正确指标；
- 是否使用正确主睡眠记录；
- 是否使用正确日期；
- 数值和单位是否正确；
- 是否错误使用个人基线；
- 数据不可用时是否正确拒绝补造。

## 4.4 Response Pass Rate

建议将“Rubric得分达到80%，且没有命中医疗安全负向项”定义为回答通过：

```text
Response Pass Rate
= Rubric得分≥80%且无安全扣分的Case数
÷ 全部可回答Case数
```

## 4.5 End-to-End Pass Rate

同时满足以下条件才算端到端通过：

1. Routing严格正确；
2. Retrieval正确；
3. Response Rubric得分达到80%；
4. 没有安全越界；
5. 没有编造个人数据。

```text
End-to-End Pass Rate
= 全链路通过Case数
÷ 全部Case数
```

这是最适合写进AIPM简历的整体产品指标。

## 4.6 Safety Recall与误拦截率

```text
Safety Recall
= 成功拦截的高风险Case数
÷ 全部高风险Case数
```

```text
False Positive Rate
= 被错误拦截的正常问题数
÷ 全部正常问题数
```

如果只有10条安全Case，简历必须同时写明样本量：

> 在10条高风险测试集和40条正常问题集上，实现安全风险召回率X%、正常问题误拦截率Y%。

不要只写“高风险识别率100%”而不说明样本规模。

## 4.7 延迟与Token

建议记录：

- Router平均耗时；
- Generator平均耗时；
- End-to-End平均耗时；
- P95端到端耗时；
- 单Case平均Prompt Tokens；
- 单Case平均Completion Tokens；
- JSON空响应与重试次数。

这些指标不一定要放进最终简历，但可以帮助回答面试官关于模型成本和用户体验的问题。

---

# 五、建议建立的7类Bad Case

## 5.1 Task识别错误

例如把健康科普识别成个人数据查询。

## 5.2 Prototype选择错误

例如“睡了多久”错误进入P01而不是P02。

## 5.3 Parameter抽取错误

例如把“几点醒来”识别成 `awake_time`，而不是 `bedtime_end`。

## 5.4 Answerability或安全策略错误

例如正常问题被拒答，高风险问题被放行。

## 5.5 Retrieval错误

包括日期、主睡眠、指标、单位、趋势窗口或个人基线选择错误。

## 5.6 回答结构与事实错误

包括没有直接回答、错误换算、编造个人数据、无依据增加洞察。

## 5.7 医疗安全与不确定性错误

包括诊断疾病、给出确定性因果、输出统一正常值或处方建议。

最终统计表建议采用：

| Bad Case类型 | Baseline数量 | 优化后数量 | 减少数量 |
|---|---:|---:|---:|
| Task错误 | [X] | [X] | [X] |
| Prototype错误 | [X] | [X] | [X] |
| Parameter错误 | [X] | [X] | [X] |
| Policy错误 | [X] | [X] | [X] |
| Retrieval错误 | [X] | [X] | [X] |
| 回答结构/事实错误 | [X] | [X] | [X] |
| 医疗安全错误 | [X] | [X] | [X] |

---

# 六、七天执行计划

## 第1天：冻结评测口径

完成：

- Routing Exact Match定义；
- Parameter Accuracy定义；
- Retrieval Accuracy定义；
- Response Pass和End-to-End Pass定义；
- Safety Recall和False Positive Rate定义；
- 批量评测结果表结构；
- Prompt和模型版本记录方式。

产出：一张可以记录每条Case结果的Evaluation表。

## 第2天：扩充到50条Case

重点覆盖：

- 标准表达；
- 口语表达；
- 同义改写；
- 模糊表达；
- 边界表达；
- 高风险与拒答表达；
- 容易发生Prototype混淆的表达。

可以使用模型辅助生成表达，但每条问题、Expected Routing、Expected Parameters和Rubric必须人工审核。

## 第3天：运行Baseline

在不修改Router Prompt和业务规则的情况下先运行一次当前版本，记录：

- Routing Accuracy；
- Parameter Accuracy；
- Retrieval Accuracy；
- Response Pass Rate；
- End-to-End Pass Rate；
- Safety Recall；
- False Positive Rate；
- 各类Bad Case数量；
- 平均与P95耗时；
- 平均Token和重试次数。

Baseline必须保留，不能为了数字好看而覆盖。

## 第4天：优化Routing与歧义处理

优先处理：

- P01与P02边界；
- P05与P14边界；
- P07与“个人数值是否正常”问题的边界；
- `awake_time`与`bedtime_end`；
- 正常问题、安全问题和范围外问题；
- Router Parameters Schema校验；
- 高置信度确定性规则与低置信度LLM分类的边界。

## 第5天：优化回答与安全

优先处理：

- 结论前置；
- 个人基线；
- 时间与时长换算；
- 禁止补造数据；
- 医疗不确定性；
- P07知识边界；
- 高风险问题升级；
- 回答长度与冗余。

## 第6天：团队试用

建议邀请3—5人：

- 每人运行6—10个问题；
- 累计完成30—50次Run；
- 记录是否看懂回答；
- 记录问题是否被正确理解；
- 记录能否通过Workflow定位失败节点；
- 收集真实用户表达进入回归集。

如果条件允许，可以设计5—10个预埋错误，让参与者分别使用旧Debug JSON和Workflow Studio定位，记录中位定位时间。

## 第7天：最终回归与简历更新

使用完全相同的50条Case重新运行，得到：

- Baseline到Final的准确率变化；
- 各类Bad Case减少数量；
- 安全召回与正常问题误拦截；
- 端到端通过率；
- 延迟和Token变化；
- 团队试用数据；
- 仍未解决的问题清单。

最后只将真实测得的结果替换进简历。

---

# 七、七天回归数据记录模板

## 7.1 整体指标

| 指标 | Baseline | Final | 变化 |
|---|---:|---:|---:|
| Case数量 | [X] | [X] | — |
| Routing Exact Match Accuracy | [X%] | [Y%] | [+Z pp] |
| Parameter Accuracy | [X%] | [Y%] | [+Z pp] |
| Retrieval Accuracy | [X%] | [Y%] | [+Z pp] |
| Response Pass Rate | [X%] | [Y%] | [+Z pp] |
| End-to-End Pass Rate | [X%] | [Y%] | [+Z pp] |
| Safety Recall | [X%] | [Y%] | [+Z pp] |
| False Positive Rate | [X%] | [Y%] | [-Z pp] |
| 平均端到端耗时 | [X秒] | [Y秒] | [变化] |
| P95端到端耗时 | [X秒] | [Y秒] | [变化] |
| 平均Token | [X] | [Y] | [变化] |

## 7.2 原型级指标

| 原型/任务 | Case数 | Baseline准确率 | Final准确率 | 主要Bad Case |
|---|---:|---:|---:|---|
| P01 | [X] | [X%] | [Y%] | [填写] |
| P02 | [X] | [X%] | [Y%] | [填写] |
| P05 | [X] | [X%] | [Y%] | [填写] |
| P07 | [X] | [X%] | [Y%] | [填写] |
| P11 | [X] | [X%] | [Y%] | [填写] |
| P12 | [X] | [X%] | [Y%] | [填写] |
| P14 | [X] | [X%] | [Y%] | [填写] |
| P25 | [X] | [X%] | [Y%] | [填写] |
| Out-of-scope/诊断/用药 | [X] | [X%] | [Y%] | [填写] |

---

# 八、七天后可替换的强量化简历模板

所有方括号必须使用真实运行结果替换。

- 基于 **[50]条** 睡眠与健康问题构建覆盖 **[8类回答原型+3类安全任务]** 的回归测试集，归纳Prototype误判、参数抽取、策略越界、数据检索、事实错误、回答结构和医疗安全等 **[7类] Bad Case**。

- 通过迭代Router Prompt、原型边界、参数Schema和确定性消歧规则，使Routing Exact Match Accuracy由 **[X%]提升至[Y%]（+[Z]个百分点）**，Parameter Accuracy由 **[X%]提升至[Y%]**。

- 建立Routing、Retrieval、Response Rubric与安全规则的端到端评测口径，使全链路Case Pass Rate由 **[X%]提升至[Y%]**，高风险测试集召回率达到 **[X%]**，正常问题误拦截率控制在 **[Y%]**。

- 将回答过程拆解为 **12个运行节点和5个评测节点**，支持节点级输入输出、Prompt、Token和源码追踪；推动 **[N名]团队成员累计完成[M次]试用Run**，将单条Bad Case中位定位时间由 **[X分钟]缩短至[Y分钟]**。

- 扩展P07受控睡眠知识库至 **[N个]词条**，通过结构化知识检索和禁止表述规则，将健康科普类回答Rubric通过率由 **[X%]提升至[Y%]**。

---

# 九、最终简历优先保留的数字

简历空间有限，七天后不要堆砌全部指标。优先保留：

1. **50条回归Case**；
2. **7类Bad Case**；
3. **Routing Accuracy：X% → Y%**；
4. **End-to-End Pass Rate：X% → Y%**。

再根据JD选择性补充：

- 8类回答原型；
- 12个运行节点+5个评测节点；
- 34项Rubric；
- 11个或扩展后的P07词条；
- 14项或扩展后的自动化测试；
- 团队人数与运行次数；
- Bad Case定位时间缩短比例；
- 高风险召回率和误拦截率。

---

# 十、不能提前写进简历的内容

在实际批量回归前，不要写：

- Routing Accuracy由某个百分比提升至某个百分比；
- 已经归纳7类Bad Case，但没有完成实际分类统计；
- 高风险识别率100%，但没有说明样本数量；
- 团队效率提升XX%，但没有前后对照；
- 已经上线或服务真实用户；
- 已经形成生产级医疗合规系统；
- 医学、法务和算法团队已经完成审核；
- 业务转化率、留存率或用户满意度提升，但项目尚未真实上线。

今天提交简历时使用本文第二部分的当前真实版本。未来7天完成回归后，再用第八部分的模板替换为真实的强量化版本。

