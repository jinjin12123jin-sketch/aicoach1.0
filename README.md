# AI Coach Lab v0.1

当前已注册并跑通八个原型：

- **P01 单项数据查询**：效率、心率、HRV、呼吸率等非时长数值
- **P02 时间点与时长查询**：几点睡着、睡了多久、深睡/REM多久
- **P05 多指标日/夜汇总**：如“我昨晚睡得怎么样？”
- **P07 指标概念解释**：REM、深睡、睡眠效率、HRV等术语
- **P11 周期趋势比较**：最近N次与此前N次主睡眠比较
- **P12 个人基线偏离判断**：当前值与近7次个人平均比较
- **P14 睡眠同域综合分析**：只用睡眠数据和个人基线解释“为什么”
- **P25 风险症状识别与就医分流**：由确定性高风险预检优先拦截

P07 当前是可运行的产品草案：知识来自 `config/knowledge/sleep_terms.json`，DeepSeek只负责路由与组织语言，不应凭模型记忆补充医学结论。词条尚未完成医学审核。

本机优先读取私有的 `data/normalized/sleep_sessions.csv`；该文件和原始健康数据不会进入公开仓库。团队首次克隆时会自动回退到 `data/demo/synthetic_sleep_sessions.csv`，Demo 默认 Query Context Date 为 **2026-05-07**。

## 运行链路

用户问题  
→ 确定性高风险预检  
→ LLM Router 输出 Task + Prototype + Parameters  
→ Policy Engine 按回答规则库决定是否可回答  
→ Python 按原型查询真实睡眠数据  
→ Insight Engine 计算可溯源洞察  
→ 生成个人近7次主睡眠基线  
→ P02 Answer Planner 组装必答事实、默认信息包与安全候选  
→ Candidate LLM 生成 AI Coach 回答  
→ P02 Validator 校验事实、话术与边界（失败时重写一次）  
→ LLM Judge 按 Rubric 逐条判分  
→ Routing Score + Response Rubric Score + Bad Case

## Workflow Studio

页面已经升级为只读的三栏工作台：

- **Workflow Studio**：左侧浏览全部Python/JSON资源，中间显示本次12节点执行链路，右侧查看对话、节点输入输出、模型元数据和对应源码。
- **Evaluation**：选择语义匹配的Bench Case，运行可点击的5节点Evaluation Workflow。
- **Run History**：重新打开本机历史Run；旧版Trace会自动转换为兼容节点视图。

运行节点定义及文件映射位于 `config/workflow_modules.json`；统一Trace由 `backend/workflow_trace.py` 生成。页面不允许修改源码或改变连线，`.env` 和API Key不会进入文件浏览或Trace。

## Bench Cases

- P02：9条（覆盖入睡、醒来、总睡眠、卧床、深睡、REM、清醒、入睡潜伏期及口语表达）
- P05：2条（标准/口语表达）
- P07：2条（REM、HRV概念解释）
- P11/P12/P14/P25：各1条基础Case

运行自动测试：

```bash
python -m unittest discover -s tests -v
```

运行指定 Case：

```bash
python -m scripts.run_single_eval --case-id SLEEP_P07_001
```

## API 最后再填即可

复制 `.env.example` 为 `.env`，最后填写：

```text
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=...
DEEPSEEK_MODEL=...
```

## 启动

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 当前限制

- v0.1 Candidate 和 Judge 可以暂时使用同一个 DeepSeek 模型，因此存在 Judge Bias。
- “昨晚”“7日基线”“睡得怎么样”的产品口径均在 `config/product_decisions.json` 标记为 provisional。
- P07术语库是 `product_draft_not_medically_approved`，上线前必须由医学、法规和设备算法团队审核，并为版本、适用设备与引用来源建立变更记录。
- 症状咨询、诊断与用药请求仍不开放自由回答；P25目前只做规则预检与风险分流，不代替医疗服务。

## 产品可配置位置

- `config/answerability_rules.json`：哪些任务允许回答、拒答或升级。
- `config/prototypes.json`：Task 与原型的对应关系。
- `config/metric_profiles.json`：P02四个指标族、默认信息包和展示门槛。
- `config/metric_relationships.json`：P02允许进入候选的关系及表达边界。
- `config/answer_style_rules.json`：P02回答深度、禁止开场、隐藏元数据和无依据评价词。
- `config/health_claims.json`：允许使用和禁止使用的健康表述。
- `config/knowledge/sleep_terms.json`：P07受控睡眠术语库、别名、边界与来源。
- `config/rubrics/*.json`：每个原型的满分回答与扣分规则。
- `backend/prompts.py`：Router 和 Candidate 的模型指令；它描述规则，但不独立执行分类。
- `config/workflow_modules.json`：工作流节点、模块目录与源码映射。
- `backend/workflow_trace.py`：节点状态、输入输出、耗时、来源文件和敏感字段脱敏。
