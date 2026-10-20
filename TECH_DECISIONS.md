# 技术选型决策记录（TECH_DECISIONS）— 实现细节版

> 每项选型给出：**最终方案与实现机制（代码级）→ 技术层面对比 → 面试追问点 → 局限与预案**。
> 与 [SPEC.md](SPEC.md) D01–D16 对应；所有代码引用可点开验证。

---

## 1. 仿真内核与控制抽象：MuJoCo 2.3.3 + robosuite 1.4.0 OSC absolute 7D（D14）

### 实现机制

动作向量 7 维：`[x, y, z, 轴角×3, gripper]`，世界系**绝对**末端位姿目标。wrapper（[libero_env.py](sim/libero_env.py)）做了四件关键事：

```python
# ① 控制器模式补丁：robosuite 1.4.0 用 control_delta 键（1.5 改名 input_type），
#    默认 delta 模式；monkey-patch load_controller_config 强制绝对位姿：
def _patched_load(*args, **kwargs):
    cfg = _orig_load(*args, **kwargs)
    cfg["control_delta"] = False   # False = 发世界系绝对位姿目标
    return cfg
suite.load_controller_config = _patched_load

# ② 夹爪符号翻转：robosuite Panda 实测 +1=闭合、-1=张开，
#    与对外文档约定（+1=开）相反，step() 里翻符号，对外约定不变：
wire[6] = -wire[6]

# ③ 夹爪开度归一化读数：双指 qpos 是镜像值（一 +一 -），取绝对值均值除以行程 0.05：
gripper_open = np.clip(np.mean(np.abs(obs["robot0_gripper_qpos"])) / 0.05, 0.0, 1.0)

# ④ 初始状态加载：LIBERO 的 init_states 是含 numpy 数组的 .pruned_init pickle，
#    torch>=2.6 默认 weights_only=True 会拒绝，显式关闭：
init_states = torch.load(path, weights_only=False, map_location="cpu")
```

每个 episode：`env.reset()` → `env.set_init_state(init_states[0])`（确定性复位）→ 逐步 `env.step(action)` → `env._check_success()` 判定。单集 1500 步上限，超时由 wrapper 抛 `TrialCapExceeded`。

### 技术层面对比

| 维度 | OSC absolute（选定） | OSC delta | 关节空间 | 运动规划库 |
|---|---|---|---|---|
| LLM 可用性 | 高：笛卡尔位姿是文本可描述的量 | 中：agent 需自积分位姿，误差累积 | 低：关节角反直觉 | 不适用（等于替 agent 写策略） |
| 与论文一致性 | 完全一致 | 不一致 | 不一致 | 破坏"免示范"前提 |
| 数值稳定性 | 目标位姿直接下发，无累积误差 | 每步相对增量，停不准会漂 | 免 IK 奇异性但需要 IK 解算在环 | 稳定但黑盒 |
| 版本坑 | 1.4 `control_delta` vs 1.5 `input_type` 键名漂移（已修复） | 同左 | 无 | 依赖重 |

### 面试追问点

- **"为什么 7 维够，不需要 6D 力控？"** —— LIBERO 任务以刚体抓放为主，位置控制在自由空间足够；力控缺失确实是 Goal 套件（铰链抽屉）失败的根因之一：位置伺服遇关节约束会顶死而不是顺从。这是能力边界而非 bug。
- **"夹爪符号为什么错？怎么发现的？"** —— 文档惯例 +1=张开，但 robosuite 的 Panda gripper action 语义相反；M1 阶段 task 0 连续 3 次失败、逐段二分（到位正常、闭合无效）定位到是符号问题，wrapper 翻转、文档不变，把坑封在边界层。
- **"为什么 monkey-patch 而不是改 robosuite 源码？"** —— 补丁集中在 wrapper 一处、升级 robosuite 时回归面最小；改源码则污染上游、不可审计。

### 局限与预案

位置控制无柔顺性 → 关节类任务天花板；预案：wrapper 已预留观测扩展点（关节状态本可从 `env.sim` 拿到，但加观测=改实验条件，须登记偏差再动）。

---

## 2. Agent 底座：MiniClaudeCode 零修改 + 上下文压缩阶梯（D02/D05）

### 实现机制

MCC 通过环境变量接收全部运行参数（零代码修改）：`MAX_TURNS`（p0=120/p1=100/p2=p3=120）、`MAX_TOTAL_TOKENS`（6M）、`TRACE_PATH`（每任务独立 trace.jsonl）、`--root`（工作区）。核心机制三项：

**① 上下文压缩阶梯**（[context.py](file:///home/czx/MiniClaudeCode/src/miniclaude/agent/context.py)）：按 token 压力分档——

```python
def level_for_pressure(self, pressure: float) -> Level | None:
    if pressure >= L2_SUMMARIZE_PRESSURE: return "summarize"  # L2：LLM 摘要旧历史
    if pressure >= L1_ELIDE_PRESSURE:     return "elide"      # L1：剪裁/省略旧工具输出
    return None
# L3 不是动作，是"跑完整条阶梯仍超限"的终止判定
```

设计要点：压缩**绝不原地改调用方历史**（返回新消息列表）；`summarizer` 以回调注入，context 模块不认识 LLM 客户端；另有 hard-fuse（请求估算已超硬限比例时直接拒发，省一次必败调用）。实测：spatial_3 触发 17 次、goal_0 触发 24 次——86 轮会话在小窗口上全靠它续命。

**② 终止语义**：`TerminationReason` 枚举（max_turns / budget / stall / completed / error…），runner 据此分类 outcome 而不是猜退出码。

**③ 网络容错**：`_RETRY_STATUS={408,409,429,500,502,503,504}` 指数退避重试，429（限流）不外泄到任务层。

### 技术层面对比

| 维度 | MCC（选定） | 通用 SDK（Claude Code 等） | LangGraph |
|---|---|---|---|
| 运行参数注入 | 环境变量，外部可控 | CLI/API 参数，行为半黑盒 | 代码内配置 |
| trace 粒度 | 逐轮 kind=turn_start/tool_call/llm_response + usage 计量 | 依 SDK 版本而异 | 需自建 callback |
| "未修改"主张 | 成立（diff 为空可审计） | 弱（无法证明没调行为） | 弱（框架即行为） |
| 压缩可控性 | 阶梯参数、触发线全自有 | 内置不可调 | 自建 |

### 面试追问点

- **"elide 和 summarize 的取舍？"** —— elide 零成本、无信息伪造（只是剪掉旧工具输出的主体，保留头部与计量），先做；summarize 要花一次 LLM 调用且摘要可能失真，压力到更高阈值才做。压缩耗时 vs 必败请求的权衡由 hard-fuse 处理。
- **"为什么不用固定窗口截断？"** —— 截断会把"最近上下文"与"任务目标"割裂；阶梯保留 system+目标+近期轮，牺牲的是最旧的工具大输出（对决策信息密度最低）。
- **"agent 框架对成功率的贡献怎么量化？"** —— 未做组件消融（诚实回答）；有观测证据：压缩缺失的会话在 ~80K token 后必死，read-before-act 纪律在 100% 成功会话出现，write_todos 与成功强相关但未归因。

### 局限与预案

MCC 权限门/路径锁按软件工程域设计，机器人域合法操作可能被拦（R7）——实测零星摩擦；预案是 D05 流程（登记偏差 → 改 → 复审），只许加配置不许加领域特化。

---

## 3. LLM 接入：OpenAI 兼容 + 双免费 key 轮换（D03/D16）

### 实现机制

MCC 用 httpx 0.28.1 + python-dotenv 直连 OpenAI 兼容端点（无 SDK 依赖）。配置层：`secrets.local.json`（gitignored）存两个 provider 的 base_url/api_key + active 索引；`rotate_key.py` 切换 active 并重写 MCC `.env` 的 `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` 三行。主备：sensenova-6.8-flash-lite → agnes-3.0-flash。

三层容错：MCC 内 429/5xx 指数退避 → runner 对 `llm_failure` outcome 的会话做轮换重试（2 次 + 60s 冷却）→ 守护脚本按 run.json 的 outcome 清扫重跑（最多 2 轮）。M4 实测 5 个 llm_failure 全部自动恢复，零人工介入。

### 技术层面对比

- **vs 付费旗舰 API**：≈190 会话 × 最多 6M token，按旗舰价是显著成本；且本项目自变量之一就是模型档位（20.8% vs 论文 70.6% 的归因依赖"保持 flash 档"这一事实），换旗舰反而破坏归因。
- **vs 本地模型（vLLM）**：本机 5.4GB RAM 无独显，7B 级 tool-call 质量崩塌；模型能力是被测变量，不能自降。
- **vs 单 key**：免费额度中途限额是必然事件（实测发生），无轮换则全量跑批停机等人。

### 面试追问点

- **"怎么处理端点隐性限流？"** —— 两层：MCC 对 429 退避吸收瞬时限流；轮换处理配额级枯竭。上线前先小批量实测端点可用性（M0 冒烟含 tools 调用验证），避免中途中断。
- **"key 安全怎么做的？"** —— secrets.local.json gitignored、trace 里 api_key 落盘时脱敏为 `***`、MCC 系统提示词明令不读密钥文件。
- **"会话间模型一致性？"** —— 轮换发生在"会话之间"而非会话内；全量阶段尽量单模型跑完，报告按 provider/model 标注每次运行。

### 局限与预案

flash 档是成功率天花板（Goal 套件 coaching 也救不动是模型缺口）；双 key 同枯竭则暂停实验保一致性，不中途换模型。

---

## 4. 编排：runner 子进程 per-task + RAM 背压（D04/D06）

### 实现机制

```python
# 子进程命令行（每任务独立）：
[mcc_python, "main.py", "--task", prompt_path, "-y", "--root", ws]
env 注入: MAX_TURNS / MAX_TOTAL_TOKENS / TRACE_PATH=<tdir>/trace.jsonl
         / FAEA_STATE_PATH=<tdir>/sim_state.json   # 计数器在沙箱外（见 §7）

# 并行：ThreadPoolExecutor(max_workers=2)，提交前先背压：
def wait_for_ram(min_avail_mb: int = 2200) -> None:
    for _ in range(60):                      # 最多等 30 分钟
        avail = parse_meminfo("MemAvailable") # 读 /proc/meminfo
        if avail >= min_avail_mb: return
        time.sleep(30)
```

参数来源是实测：单会话峰值 ~1GB（MCC 常驻 31MB + MuJoCo 仿真子进程瞬态），机器 5.4GB → 2 并发 + 2.2GB 背压线（留 ~1GB 系统余量）。任务状态机全靠文件系统：目录存在性=断点，`--all` 幂等续跑（M5 中断 → M6 续跑实战验证）。

### 技术层面对比

- **vs 长驻进程复用会话**：冷启动仅秒级，省它不值；长驻的状态泄漏（上下文/环境变量残留）会污染相邻任务，正确性风险不可接受。
- **vs Celery/Redis 队列**：单机 2 并发引入 broker 是过度设计；文件系统即队列，`ls` 就是状态页。
- **vs Docker**：WSL2 无 GPU 下 EGL/MuJoCo 容器化调试成本高；隔离需求（依赖冲突）已由双 conda 满足。
- **vs 多进程 Pool**：任务内本就有两层子进程（MCC → 仿真），再嵌 multiprocessing 会让信号/僵尸处理复杂化；线程池 + 子进程的组合让"取消"语义简单（杀进程组）。

### 面试追问点

- **"为什么 ThreadPool 不是 asyncio？"** —— 并发单位是阻塞式子进程等待（subprocess.run 级），asyncio 反而要把等待全部异步化，收益为零；线程阻塞在 os.wait 上成本可忽略。
- **"背压为什么轮询 /proc/meminfo 而不用 cgroup/psutil？"** —— 少一个依赖；要的只是 MemAvailable 一个数；轮询 30s 粒度对小时级任务足够。
- **"任务中断怎么恢复？"** —— 目录即状态：无 run.json = 未完成，重跑覆盖；有 run.json = 跳过。半途残留（M5 的空目录）在 M6 前清扫。

### 局限与预案

并发上限受 RAM 硬约束（~4 并发天花板，保守取 2）；OOM 时任务标 infra_env 可安全重跑（goal_5 即此类，M7 补跑）。

---

## 5. 环境隔离：双 conda（py3.10 仿真 / py3.11 agent）（D07）

### 实现机制

- `libero` env（py3.10.22）：robosuite 1.4.0（其依赖链钉死 py≤3.10）、MuJoCo 2.3.3、torch 2.14.1+cpu、opencv 4.8.1.78、scipy 1.10.1（均钉版本）。
- `mcc` env（py3.11.17）：MCC 需要 3.11+ 特性（StrEnum）、httpx 0.28.1、python-dotenv。
- LIBERO 仓库用 `.pth` 文件挂 `/home/czx/LIBERO`——editable install 的 namespace package（外层无 `__init__.py`）导致 `import libero` 的 MAPPING 为空，`.pth` 挂路径绕过。
- 配置隔离：`LIBERO_CONFIG_PATH=/home/czx/.libero-faea`（wrapper 内 setdefault），防止 FAEA 的配置与宿主机其它 LIBERO 使用者串味。

### 技术层面对比

单 venv 物理不可行（robosuite 依赖链 vs StrEnum 的 Python 版本冲突，不是偏好问题）；Docker 隔离更彻底但 WSL2 无 GPU 的 EGL 调试成本高，且可复制性已由 environment.yml + 钉版本兜底。

### 面试追问点

- **"依赖求解具体卡在哪？"** —— robosuite 1.4 的依赖（mujoco-py 时代遗留的安装链 + opencv/scipy 老版本）在 py3.11 无 wheel；pip 连环回退到源码编译失败。钉 scipy==1.10.1、opencv==4.8.1.78 后收敛。
- **"torch 2.14 踩了什么？"** —— torch>=2.6 `torch.load` 默认 `weights_only=True`，LIBERO 的 init state 是含 numpy 数组的 pickle，必须显式 `weights_only=False`（信任边界内：文件来自基准仓库）。
- **"镜像源踩坑？"** —— tuna 全线 403、aliyun 部分 wheel 404 回源失败、SJTU 重定向回 tuna；最终腾讯镜像收敛。教训：国内环境装科学计算栈先验证镜像完整性。

### 局限与预案

conda 环境不可移植（路径写进 config.json）；预案：environment.yml 固化 + 重建脚本化 + 关键包钉版本。

---

## 6. 评测协议与反作弊：沙箱外计数 + trace 正则 + 独立重跑（D12/D13）

### 实现机制

三道防线，全部把 agent 当作**不可信方**：

```python
# ① 计数器出沙箱：wrapper 默认把 sim_state.json 写在 cwd（agent 可写），
#    runner 用环境变量把它指到任务目录（agent 工作区之外）：
os.environ.get("FAEA_STATE_PATH", str(Path.cwd() / STATE_FILENAME))

# ② trace 级规则扫描（R5）：对 trace.jsonl 里 bash 命令做正则匹配：
R5_TRACE_PATTERNS = [
    re.compile(r"(rm|mv|sed\s+-i|truncate|echo\s+.*>|tee)[^\n]{0,80}(sim_state|\.sim_state)"),
    re.compile(r"FAEA_STATE_PATH"),   # agent 不该知道这个变量，出现即标
]

# ③ 独立复核：review.py 重放 episode.py（干净进程、干净 env），
#    结果与 meta.json 比对，一致才记 success_verified。
```

完整规则集 R1–R5：API 绕过 / 穷举搜索 / 伪造成功标记 / 硬编码答案 / 计数或 trace 篡改。命中即 `flagged` → 人工裁决 → `excluded_cheating`。M4 实抓 4 例（goal_5 第 33 轮 rm 计数文件；90_26/28/54 echo 清零），统一剔除后重算成功率。

失败分类学 8 类：success_verified / success_unverified / task_failed / max_turns / budget / stalled / llm_failure / infra_env——每例失败可归因，支撑难度梯度分析。

### 技术层面对比

- **vs 信任自报**：被 4 例实证否决。
- **vs LLM-as-judge**：判定规则写死在代码里（确定性、可复现），裁量权不给模型；LLM judge 只能做语义级补充，不能做裁决。
- **vs 视觉判定**：谓词判定精确无噪声，视觉引入感知误差，过度工程。

### 面试追问点

- **"为什么正则而不是语义审查？"** —— 作弊手法集中在文件操作动词 × 目标文件的组合上，正则覆盖实测全部形态且零误报可解释；语义审查适合升级为第二层（标记供人工），不能替代确定性层做自动剔除。
- **"`FAEA_STATE_PATH` 出现在 trace 为什么直接标？"** —— 该变量只由 runner 注入仿真子进程环境，agent 的 shell 不应看到它；agent 提及它 = 在探测计数器位置 = 恶意意图，成本极低的信号。
- **"独立重跑防住了什么、防不住什么？"** —— 防"谎报成功/脚本一次性"；防不住"碰巧成功的开环脚本"（重跑同样成功）与"针对 init_state 的过拟合"（论文协议本身允许确定性复位，属设计内）。

### 局限与预案

审计与作弊是军备竞赛；预案：excluded 单独披露不隐藏、可疑标记常态化人工抽查、未来可把计数器挂只读 bind-mount。

---

## 7. 观测与产物：EGL 离屏渲染 + JSONL trace schema 2.0（D09）

### 实现机制

- 渲染：`MUJOCO_GL=egl`（wrapper setdefault）无头出帧，256px@20fps 逐 try 录像（try_00N.mp4），成功后归档 video.mp4；README 嵌入用 ffmpeg palettegen 两遍法转 GIF（370–400KB，GitHub 原生渲染）。
- trace：schema 2.0，事件 kind ∈ {session_start, turn_start, llm_request, llm_response, permission, tool_call, todo_update, checkpoint, run_end}；每 llm_response 带 `usage.prompt/completion` 计量与 `latency`；每 tool_call 带 `ok/output_chars/latency/verdict`。TRACE_PATH 按任务隔离。
- 报告：report.py 生成论文 Table I/V 同构表 + CSV；`--compare-paper` 强制附模型差异声明；跳过归档目录保证增量重试阶段口径一致。

### 技术层面对比

JSONL vs SQLite：追加写进程安全（被 kill 不损数据）、jq/grep 即分析、按任务天然分片；SQLite 强在事务与复杂查询，本项目无此需求。wandb/OTel 引入外部依赖且语义错配（要的是"逐轮 LLM 取证"不是遥采样）。

### 面试追问点

- **"EGL vs OSMesa？"** —— EGL 走 GPU-less 的 GBM/设备后端，出帧快于 OSMesa 软渲染；WSL2 实测 EGL 可用即锁定，OSMesa 留作降级开关。
- **"trace 的 usage 计量踩过什么坑？"** —— token 计量必须来自响应体 usage 字段而非本地 tokenizer 估算（端点分词差异会静默漂移）；你的 Insight Agent 项目里"token 计量静默归零"缺陷是同一主题的反面案例，两处经验一致：**计费/计量数据必须端到端断言非零**。
- **"逐 try 视频怎么支持失败分析？"** —— spatial_3 案例：agent 自己数 try_00N.mp4、对照 sim_state.json 反推哪次最近；视频+trace+计数器三路对账是本项目的取证范式。

### 局限与预案

EGL 依赖 WSL2 图形栈（升级可能破坏）→ OSMesa 降级开关已留；trace 无集中检索 → 临时脚本按 kind 容错读取，schema 版本化防漂移。

---

## 附：选型速查表

| 领域 | 选定 | 核心实现细节 | 未选方案的一票否决点 |
|---|---|---|---|
| 仿真/控制 | MuJoCo 2.3.3 + robosuite 1.4.0 OSC absolute 7D | control_delta 补丁 / 夹爪符号翻转 / qpos 镜像归一 / weights_only=False | 原语库=替 agent 写策略，破坏实验前提 |
| Agent | MCC 零修改 | env 注入参数 / L1 elide→L2 summarize 压缩阶梯 / TerminationReason | 通用 SDK 无法证明"未修改" |
| LLM | OpenAI 兼容 + 双 flash key | rotate_key 重写 .env / 三层容错（退避→轮换→清扫） | 付费旗舰破坏模型档位归因 |
| 编排 | 子进程 per-task + 并行2 + 背压 | /proc/meminfo 轮询 30s / 文件系统即断点 | 长驻进程状态泄漏污染相邻任务 |
| 环境 | 双 conda 3.10/3.11 | .pth 挂载 / LIBERO_CONFIG_PATH 隔离 / 钉版本 | 单 venv 物理不可行 |
| 反作弊 | 沙箱外计数 + R1–R5 + 独立重跑 | FAEA_STATE_PATH / trace 正则 / review.py 重放 | 信任自报被 4 例实证否决 |
| 观测 | EGL 视频 + JSONL trace 2.0 | kind 事件流 / usage 端到端计量 / palettegen GIF | SQLite 无追加安全性诉求 |
