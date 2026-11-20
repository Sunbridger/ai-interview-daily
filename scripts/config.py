# -*- coding: utf-8 -*-
"""配置：主题、配额、数据源与推送。"""

TIMEZONE = "Asia/Shanghai"
DAILY_TOTAL = 10
TOPIC_QUOTA = {"agent": 4, "rag": 4, "fastapi": 2}
TOPIC_NAMES = {"agent": "Agent", "rag": "RAG", "fastapi": "FastAPI"}
TOPIC_ORDER = ["agent", "rag", "fastapi"]

# ---- 种子题库（GitHub，每周同步一次，只作考点线索，不复制原文） ----
SEED_REPOS = [
    "guocong-bincai/ai-interview-guide",
    "cdavid817/agent-interview",
    "km1994/LLMs_interview_notes",
    "didilili/ai-agents-from-zero",
]
SEED_SYNC_DAYS = 7
SEED_FILES_PER_REPO = 10
SEED_PER_TOPIC = 450
SEED_CLUE_COUNT = 8       # 每个主题每天提供给 LLM 的线索条数
SEED_REUSE_DAYS = 90      # 线索 90 天后可再次使用（题库本身永久去重）

# ---- GitHub issue（真实问题场景） ----
ISSUE_REPOS = [
    ("langchain-ai/langchain", "bug"),
    ("run-llama/llama_index", "bug"),
    ("qdrant/qdrant", "bug"),
    ("milvus-io/milvus", "kind/bug"),
]
ISSUE_PER_REPO = 4
ISSUE_CLUE_COUNT = 6

# ---- FastAPI 官方文档考点（issue 源枯竭，用文档提纲） ----
FASTAPI_TOPICS = [
    "依赖注入：Depends、子依赖、yield 依赖与清理",
    "async def 与同步依赖的线程池行为、阻塞调用",
    "中间件、CORS、异常处理器与请求生命周期",
    "Pydantic v2 校验、序列化与配置分离",
    "lifespan 与共享资源（连接池、模型客户端）管理",
    "SSE / StreamingResponse 与 LLM 流式输出",
    "后台任务、重试与幂等",
    "依赖覆盖的测试写法与 httpx/TestClient",
    "uvicorn/gunicorn 多进程部署与性能取舍",
]

# ---- 社区线索（低频，仅作参考） ----
JUEJIN_KEYWORDS = ["RAG 面试", "Agent 面试", "FastAPI 面试", "大模型 应用开发 面试"]
CSDN_KEYWORDS = ["RAG 面试题", "Agent 面试题", "FastAPI 面试题"]
NOWCODER_TAG = "639"   # 牛客面经 tagId，匿名接口通常返回空，作低频尝试

# ---- 去重 ----
DEDUPE_SIM = 0.55

# ---- Bark 推送 ----
BARK_GROUP = "面试题"
BARK_TTL = 86400
