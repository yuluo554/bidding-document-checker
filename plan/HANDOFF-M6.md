# HANDOFF-M6 —— 脱敏发布里程碑交接快照

> 用法（新对话续接）：`/goal 读取 <项目根>/plan/HANDOFF-M6.md 继续完成任务`（启动命令里的绝对路径由用户侧拼接，本文件内一律相对路径）。
> 落盘：2026-10-05，由完成 M5 的工作对话写入。

## 一、当前进度（M0–M5 已完成）

- **计划文档**：plan/00–06 定稿；M5 新增决策 D27（报告/图谱/serve 交付口径）已入 06；
  D7 docx 输入适配**显式顺延**、D14 参赛**已拍板：不参赛**（2026-10-05 用户确认，
  无追加交付物）——均已在 06 §二/§三闭环记录；
- **M5 交付（已验证，pytest 264 项全绿 5.4s；bench parse F1=1.0 + bench e2e PASS；
  版本 0.5.0，pyproject 与 __init__ 同步）**：
  - **`bidchecker report`**（report/__init__.py，report extra）：findings.json + cards/ +
    项目原文 → docx 评审报告。结构 = 项目概况 / 结论汇总 / 分级明细（high→mid→low→待人工）/
    依据与证据锚点 / 符合性校核矩阵 / 围标特征提示 / 签署栏 + 免责声明；
    **符合性推导为报告层口径（D27）**：符合 = 门控激活 + 引擎数据前提成立（镜像 engine
    handler 守卫）+ 无非符合结论；前提不成立 → "未复核"；联动否决项 RJ-02/03/04 未触发
    不计符合；卡片/原文缺失 → 降级注明照常生成（退出码仍 0）；
    **无外链断言 = .rels 无 TargetMode="External" + 无 w:hyperlink + 正文剥标签后无 http**；
    内容无时间戳（签署栏手填）；`--all` 展开符合项/未复核明细；
  - **围标图谱 HTML**（collusion/graph.py）：字符 5-gram shingle（剔空白）+ Jaccard 两两
    矩阵 + 对照独有共享（shingle 粒度扣除招标与其余投标）；**问题边 = detect_collusion
    同一套双信号**（图谱不另设判定口径，<3 份投标不产出同样遵守）；**布局 Python 侧
    确定性力导向烘焙坐标**（固定常量、零随机零时钟，两次构建逐字节一致）；SVG 由 JS
    innerHTML 字符串构建（规避 createElementNS 命名空间 URL 落进产物）；单文件 0 外链
    （无 script src / link / iframe / @import / src= / href= / url( / http(s)）；点击节点/边
    展开证据与行号锚点；`run --graph` 落 `<out>/collusion_graph.html`（投标 ≥2 份）；
  - **`bidchecker serve`**（webapp/__init__.py，web extra）：fastapi 单页（内联 CSS/JS），
    上传评审 /api/check（临时目录跑 run_pipeline，**llm_fallback=False 固定禁用**）+
    一键内置演示 /api/demo（项目名白名单 `^[A-Za-z0-9_-]+$`）；图谱复用 collusion.graph
    的 GRAPH_CSS/GRAPH_JS（单源）；**/docs /redoc /openapi 显式关闭**（Swagger 引 CDN）；
    0 外链断网可演示（实测 uvicorn 真启动 + curl 200）；
  - **CLI 收口**：run 0/1/2（新增 --graph）；report 0/2（降级仍 0）；serve 0/2；
    test_cli future_commands 参数化已清除并重写为转正测试；
  - **断网全链演示**：零 LLM env 下 datagen → run --graph → bench parse/e2e → report →
    serve（真实 uvicorn + curl）全链离线跑通；
  - **干净环境冒烟**：本地 clone 到新目录 + 全新 venv 按 README 快速开始逐字跑通——
    pytest 264 项全数对账、datagen --seed 42 再生成 examples/ 位级一致（git status 零差异）、
    bench parse/e2e PASS、run/report/serve 全过；
  - README 更新（report/serve/graph 命令与特性节）；CI 安装改 `[dev,report,web,llm]`
    （webapp 测试的 TestClient 依赖 llm extra 的 httpx；新测试全部 pytest.importorskip
    守卫，裸 [dev] 环境跳过不挂）；
- **git**：本地已提交至 M4（f955a46）；**M5 改动尚未提交**（本对话收尾时提交，见 §五）；
  未建远端、未 push（建仓 = M6 动作）。

## 二、下一里程碑 M6（脱敏发布）待办

1. **提交邮箱全历史改写（D13，发布门）**：`git filter-branch --env-filter` 把
   个人 QQ 邮箱全历史改写为 282769740+yuluo554@users.noreply.github.com（旧邮箱原文
   已从 plan 文档剥离，见 06 D13——历史 blob 用 tree-filter 一并洗除）；
   本地 `git config user.email` 同步改；改写后全量测试 + 双基线复跑；
2. **脱敏四步 + 三扫全 0**：
   ① plan 文档姊妹项目/系列表述复核（D15——姊妹项目均已公开则互相提及无碍，未公开则
   从 plan 文档移除系列表述）；② 代码扫描（无个人姓名/路径/内网信息）；③ 数据扫描
   （全合成主体已达标，抽验 examples/ 与 data/）；④ 密钥/凭据扫描（git log 全历史 +
   工作树；LLM 账号从未入仓，env 三件套名可保留）；
3. **建远端并 push**：GitHub 公开仓库 owner=yuluo554（D2：bidding-document-checker），
   push main；**push 数 = CI run 数对账**（D11：tag 触发暂不配）；
4. **CI 首跑诊断**：四矩阵（ubuntu/windows × 3.8/3.12）预期环境差异型问题集中爆发
   （EOL/版本/编码），预留"诊断+修复+再推"一轮；注意 M5 已改 CI extras 与
   fastapi/pydantic 在 3.12 的解析路径（模块顶层守卫导入是 3.8 兼容写法，3.12 首跑重点盯）；
5. **tag/release（经用户确认）**：v0.5.0 tag + GitHub Release（changelog = M1–M5 里程碑行）；
   tag 触发 CI 未配置（如实记录即可）；
6. **缓议收尾**：D14 参赛**已拍板不参赛**（2026-10-05，无追加交付物——技术报告/演示视频
   不做）；D15 复核结果记入 06；
7. **README 终检**：徽章/链接/快速开始与发布仓库一致；免责声明与定位段保持；
8. DoD 全过后：回写 plan/00/05/06 终态，结束会话（M6 为终版里程碑）。

## 三、既定口径清单（动了会打挂基准）

- `schema.py` 字段与结构 = plan/04 §1（M0 冻结，未动）；
- **真值语义**（datagen/__init__ 注释为权威）：注入缺陷记主期望（expect_findings），
  隐含结论记 also_expect；**e2e 对账 = 全集合含 D11（D24）**；四元组
  (rule_type, status, risk_level, target) 唯一；D4/D8/D9 → rejection_scan 隐含
  （R4/R2/R3）；D5 打 ▲ 无隐含；D12 主期望即 rejection_scan（R1）；D10 目标 tender.md；
  **D11 目标围标对（两端按投标人名排序规范化，D23）**；
- **引擎接口口径**（=D19）：run_checks 投标侧 / run_tender_checks 招标侧分侧；
  doc_text=None → only_if 规则不激活；只产非符合结论；check_id 必须在 rules.json
  注册（**21 个 CHK-\***，含 CHK-CL-01）；
- **引擎引用条文 = D20**（全部官方逐字核验）：87号令 23/36/37/39/50/59/60/63 条 +
  实施条例 25/26/27/39/40/51 条 status=已核对；招标投标法 33/34 条 status=待核对
  **引擎不引用**（D26）；16号令/195号文条文按需补；
- **围标双信号交叉验证 = D23**：SENTENCE_MIN_LEN=24；<3 份投标不产出；
  CHK-CL-01 的 rule_type=collusion 不在 RULE_TYPES 分派表内（test_gates/test_engine/
  test_knowledge 三处锁定口径）；**图谱问题边 = 同一套 detect_collusion 判定（D27）**；
- **报告层符合性推导 = D27**：符合 = 门控激活 + 数据前提成立 + 无非符合结论；
  联动项未触发不计符合；docx 无外链/无时间戳；图谱 HTML 0 外链 + 构建逐字节一致；
  serve 0 外链 + llm_fallback=False 固定禁用 + /docs 关闭；
- **LLM 兜底纪律 = D25**：槽位白名单、quote ⊂ 原文硬校验、数值合法性校验、不覆盖
  确定性抽取、LLM 不改 Finding.status、不可达降级纯规则通路、bench 强制
  llm_fallback=False（零 API）；**serve 同样固定禁用（D27）**；
- **R1 条款内嵌最高限价金额**：引擎从 R1 文本 `人民币x,xxx.00元` 抽取（schema 无预算字段）；
- ▲偏离方向语义 = D22：下限（不少于/不低于）、上限（不超过/不高于、"X日内完成"）；
  响应值更优不属偏离；数值不可提取宁缺勿错跳过；
- Finding 三级判定常量与 RULE_TYPES 7 类集合不变（test_gates 锁定）；
- `only_if` 类目门控对全部 check_type 生效（引擎分派前必过 gates.rule_applies）；
  当前 rules.json 21 条 only_if 均为空——报告层门控推导逻辑已按非空实现（D27）；
- **体例行级格式 = 解析接口**（templates.py 注释）；bench parse F1=1.0 不回退是每次
  收尾的必跑项；bench e2e PASS 同为必跑项；
- 基准门槛不放宽：解析 F1 ≥ 0.95、e2e 检出率 ≥ 0.95、误报 0、准确率 ≥ 0.95、零 API 依赖；
- **examples/ 是字节冻结 fixtures**：改体例/生成器 → test_examples_fixture_frozen 会挂，
  属预期——用 `bidchecker datagen --seed 42` 重新生成后整目录提交，**禁止手改**；
- 生成路径禁 stdlib random / set 迭代 / 系统时钟（DetRng 纪律）；落盘产物
  （findings.json、collusion_graph.html）无时间戳（两次运行/构建逐字节一致；
  docx 内容无时间戳但 zip 容器不承诺逐字节）；search.py 与图谱布局排序确定性（禁哈希序）；
- 测试全离线 mock；core 零依赖；**新测试 import extras 必须 pytest.importorskip 守卫**
  （test_report/test_webapp 模式）；CI 装 [dev,report,web,llm]；
- CLI 退出码语义（M3/M4/M5 定稿锁进 test_cli）：run 0/1/2（--graph）；bench parse/e2e 0/1；
  report 0/2（降级仍 0）；serve 0/2；参数错误 2；
- EOL：`.gitattributes` `* text=auto eol=lf`；fixtures 出现 CR 即大声失败。

## 四、本机环境坑（只记实测过的）

- **系统 Python 3.8.8 + setuptools 49.2.1 过老**：系统 env `pip install -e .` 需先
  `py -m pip install -U setuptools wheel`；**全新 venv 无此坑**（默认 build isolation
  直接成功，M5 冒烟实测）——干净环境冒烟直接按 README 走即可；
- 用 `py` 不用 `python`（商店占位符）；脚本一律 `py -X utf8`（中文控制台 GBK）；
  全程 `PYTHONDONTWRITEBYTECODE=1`（pip install 也要带）；
- pip 已配置 tsinghua 镜像；若注册表系统代理污染 → 前缀 `NO_PROXY="*" no_proxy="*"`；
  curl 抓 gov.cn/mof.gov.cn 官网页面与本地 curl 127.0.0.1 需同样前缀；
- `bidchecker.exe` 装到 `Python38\Scripts`（不在 PATH）→ 统一用 `py -X utf8 -m bidchecker`；
- Git Bash 以 `/` 开头的参数会被 MSYS 静默转写（taskkill 用 `//PID //F` 双斜杠形式）；
- Git Bash 的 `/tmp` 与 Windows Python 互不可见——curl 下载落盘用**工作区内相对路径**；
- **`py -X utf8 - <<heredoc` 含中文偶发 stdin 编码 SyntaxError**——改写为工作区临时
  .py 文件执行（用完即删）；py3.8 不支持 `{a, *b}` dict 解包（冒烟脚本实测）；
- `Path.write_text()` 在 py3.8 无 `newline` 参数——写 UTF-8/LF 统一用 `write_bytes(x.encode("utf-8"))`；
- **fastapi 端点注解不能在 create_app() 内惰性导入后配合 `from __future__ import
  annotations` 使用**（pydantic ForwardRef 无法从函数局部命名空间解析，POST 即崩
  PydanticUserError）——webapp 的 FastAPI 系类型在**模块顶层守卫导入**，惰性只留 uvicorn；
- **fastapi TestClient 需要 httpx**（starlette 依赖）——httpx 在 llm extra；CI 与 README
  快速开始装 `[dev,report,web,llm]`，否则 test_webapp 整模块静默 skip（252+1 vs 264）；
- **Git Bash 后台启动的 uvicorn（`... &`）`kill %1` 不一定杀掉 Windows 子进程**——残留
  进程占住目录导致 `rm -rf` 报 Device or resource busy；先
  `powershell Get-CimInstance Win32_Process` 按命令行确认身份再 `taskkill //PID x //F`；
- **docx 的 .rels 里 Relationship Type 属性本身是 http URI**（OOXML 规范如此）——
  "docx 无外链"断言必须查 `TargetMode="External"` + `w:hyperlink` + 正文剥标签后无 http，
  不能对 .rels 全文做 http 子串扫描；
- **gh OAuth token（gho_）无 `workflow` scope 时，push 含 `.github/workflows/*` 的提交会被拒**
  （"refusing to allow an OAuth App to create or update workflow"）——M6 实测：本机 SSH 密钥
  （id_ed25519 → yuluo554）可用，origin 改 `git@github.com:` 后 push 成功；替代方案
  `gh auth refresh -s workflow` 需交互式浏览器授权；
- **SVG 用 createElementNS 会把 `http://www.w3.org/2000/svg` 命名空间 URL 带进 HTML
  产物**，撞 0 外链断言——图谱 JS 用 innerHTML 字符串构建 SVG；
- **WebFetch 抓 flk.npc.gov.cn 返回空壳**（JS 渲染站点）；WebSearch 域名级链接不可直接
  定位全文页——逐字条文用 curl 落盘后本地提取（M4 D26 记录在案）；
- **提交元数据邮箱是个人 QQ 邮箱**（06 D13）：M6 发布前必须 filter-branch 全历史改写
  GitHub noreply，本地 `git config user.email` 同步改——**M6 DoD 第一条**。

## 五、M5 收尾动作（本对话已完成）

- pytest 264 项全绿；bench parse F1=1.0 / bench e2e PASS 不回退；版本 0.5.0；
- plan/00（M5 状态行 + 文档索引 + 决策摘要）、plan/05（M5 里程碑行 ✅）、
  plan/06（D27 + D7 顺延 + D14 状态 + 缓议表）回写；HANDOFF-M6 落盘（本文件）；
- **本地提交 M5**（不 push；建仓 push = M6 动作）。

## 六、M6 DoD checklist（终态 2026-10-05，全部完成）

- [x] 提交邮箱全历史改写（filter-branch env+tree 双滤 9 提交 → GitHub noreply）+ 本地 git config 同步 + 全量测试/双基线复跑（pytest 264 / parse F1=1.0 / e2e PASS）
- [x] 脱敏四步 + 三扫（plan 系列表述复核 D15：三姊妹均公开→保留 / 代码 / 数据 / 密钥全历史——main 仅白名单命中：env 变量名、测试 mock）
- [x] GitHub 公开仓库建立 + push main（owner=yuluo554，D2；SSH 通道，OAuth 缺 workflow scope 实测见 §四）
- [x] CI 四矩阵首跑绿（1m16s，诊断轮未动用）；push 数 = run 数 = 2 对账
- [x] tag v0.5.0 + Release（changelog=M1–M5 里程碑行）+ topics——经用户确认执行（2026-10-05）
- [x] D14 参赛已拍板不参赛（✅ 2026-10-05，无追加交付物）；D15 复核记入 06（三姊妹均公开→保留）
- [x] README 终检（CI 徽章指向发布仓库、链接/快速开始与发布仓库一致、状态行翻转 v0.5.0）
- [x] pytest 全绿（基线 264 项）；bench parse F1=1.0 + bench e2e PASS 不回退
- [x] plan/00/05/06 终态回写（D28 发布执行记录入 06）

> **M6 为终版里程碑，项目收官**（2026-10-05）。无 HANDOFF-M7；后续 docx 输入适配（D7）
> 按需另立项目。改写前全历史备份：仓外 `../bidding-document-checker-pre-m6-backup.bundle`。

## 七、关键命令速查

```bash
cd <项目根>
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest -q               # 全量测试（基线 264 项）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker bench parse  # 解析基准（F1=1.0）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker bench e2e    # e2e 基准（检出率/误报/准确率）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker run examples/demo-goods-1 --out output --graph
                                                                # 端到端 + 围标图谱（out/collusion_graph.html）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker report output/findings.json --all
                                                                # docx 报告（--all 展开符合项）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker serve --port 8000   # Web 面板（断网可演示）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker datagen --seed 42   # 再生成 examples/（位级一致）
# Web 面板测试（TestClient 走 httpx，装 llm extra 后 264 项全跑）：
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -X utf8 -m pip install -e ".[dev,report,web,llm]" --no-build-isolation
# M6 邮箱改写（发布门，先备份 bundle 再执行；旧邮箱原文不落本文件——见 06 D13）：
#   OLD_EMAIL = 06 D13 记录的旧个人邮箱（执行时以字面量代入）；NEW_EMAIL = 下方 noreply 地址
git filter-branch -f \
  --env-filter '
    OLD_EMAIL="（执行时以 06 D13 记录的旧邮箱字面量代入）"
    NEW_EMAIL="282769740+yuluo554@users.noreply.github.com"
    if [ "$GIT_AUTHOR_EMAIL" = "$OLD_EMAIL" ]; then export GIT_AUTHOR_EMAIL="$NEW_EMAIL"; fi
    if [ "$GIT_COMMITTER_EMAIL" = "$OLD_EMAIL" ]; then export GIT_COMMITTER_EMAIL="$NEW_EMAIL"; fi
  ' \
  --tree-filter 'grep -rIl "OLD_EMAIL_LOCAL_PART" . 2>/dev/null | xargs -r sed -i -e "s/OLD_EMAIL/NEW_EMAIL/g" -e "s/OLD_EMAIL_LOCAL_PART/[redacted]/g"' \
  -- --all
git config user.email "282769740+yuluo554@users.noreply.github.com"
# 三扫（M6；qq\.com 用转义写法避免模式自命中）：
git log --all -p | grep -inE "qq\.com|sk-[a-z0-9]|api[_-]?key\s*[:=]"   # 密钥/个人信息（应零命中；env 三件套变量名为白名单）
grep -rinE "construction-drawing|power-operation|medical-record" plan/ src/ README.md data/  # 姊妹项目表述（D15 已复核：三姊妹均公开→保留）
# 重装（先升级构建链；系统 env 才需要）：
NO_PROXY="*" no_proxy="*" py -m pip install -U setuptools wheel
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -X utf8 -m pip install -e ".[dev,report,web,llm]" --no-build-isolation
```
