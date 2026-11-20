# AI 面试题日报

每天 08:00（北京时间）通过 Bark 推送 10 道中高级 AI 应用面试题（Agent 4 / RAG 4 / FastAPI 2），题目来自真实工程问题，答案按 **why / how / 真实场景 / 追问** 结构化给出，并沉淀进全局题库永久去重。

- 每日页：`https://<owner>.github.io/ai-interview-daily/<YYYY-MM-DD>.html`
- 题库页：`https://<owner>.github.io/ai-interview-daily/bank/`（搜索 + 主题/难度/来源筛选）

## 题目来源

| 层 | 来源 | 用法 |
|---|---|---|
| 面经线索 | `guocong-bincai/ai-interview-guide`、`cdavid817/agent-interview`、`km1994/LLMs_interview_notes`、`didilili/ai-agents-from-zero` | 每周同步考点线索，题目与答案完全原创改写 |
| 面经线索 | 掘金 / CSDN 搜索接口 | 低频发现社区热词 |
| 面经尝试 | 牛客公开接口 | 低频尝试，返回空不影响产出 |
| Issue 场景 | LangChain / LlamaIndex / Qdrant / Milvus 的已解决 issue | 提炼「现象—原因—方案」 |
| FastAPI | 官方文档考点清单 + LLM | issue 源枯竭，按依赖注入、异步、流式等考点自建 |

## 答案结构

每题一个 Markdown 文件（`bank/<topic>/<id>.md`），包含：

- **why**：为什么会有这个问题（工程背景、原理、常见误区）
- **how**：可落地的分步方案 + 关键 Python 代码
- **真实场景**：具体症状、指标与排查路径（不编造公司名与数据）
- **面试官追问**：1–2 个追问与回答要点
- 可选的 Mermaid 图（本地渲染）

## 去重

1. 与题库同主题标题做字符相似度筛选（阈值 0.55）
2. 疑似重复交 deepseek-chat 复核，判重即弃
3. 素材不足时宁缺勿滥，少于 10 道照发

## 目录

```
bank/               题库：Markdown + index.json
data/seed/          种子线索缓存与使用记录
docs/               每日页 / index.html / bank/ 题库页 / vendor 本地 Mermaid
scripts/            抓取、生成、渲染
.github/workflows/  每日定时任务
```

## 部署

1. 新建 public 仓库并推送本目录。
2. Settings → Pages：Deploy from a branch，`main` / `/docs`。
3. Settings → Secrets and variables → Actions：
   - `DEEPSEEK_API_KEY`
   - `BARK_ENDPOINT`（形如 `https://api.day.app/<key>`）
4. Actions → daily-interview → Run workflow 手动首跑。

每天 07:30 触发，08:00 前送达；`workflow_dispatch` 可随时重跑。

## 本地运行

```bash
uv venv && uv pip install -r requirements.txt
npm install            # Mermaid 语法校验

# 只抓线索
.venv/bin/python -m scripts.main --fetch-only --date 2026-11-21

# 预览页面（不调 LLM、不写题库、不推送）
.venv/bin/python -m scripts.main --dry-run --date 2026-11-21

# 完整运行
DEEPSEEK_API_KEY=sk-xxx BARK_ENDPOINT=https://api.day.app/<key> \
  .venv/bin/python -m scripts.main
```

需要代理时显式设置 `HTTPS_PROXY`；GitHub Actions 内不需要。

## 合规

- 面经只提取考点作灵感，题目与答案原创；保留 ≤200 字原创摘要与来源链接；不搬运图片与原文
- 不使用禁止转载/需登录且条款禁止的站点（知乎、小红书、公众号）
- issue 内容仅作为场景线索重写，不整段复制

## 限制

- GitHub 种子仓库内容质量参差，线索只作灵感，答案由 LLM 生成后需自行判断
- 牛客匿名接口通常返回空，中文社区面经覆盖有限
- Mermaid 客户端渲染依赖本地 5.5MB 脚本（仅含图页面加载）
- 成本：deepseek-reasoner 每天约 ¥1 以内
