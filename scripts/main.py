# -*- coding: utf-8 -*-
"""入口：同步线索 → 生成题目 → 写题库 → 渲染页面 → Bark 推送。"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from . import bank, config, generate, render, sources

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
BANK = ROOT / "bank"


def page_base():
    explicit = os.environ.get("PAGES_BASE_URL", "").rstrip("/")
    if explicit:
        return explicit
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner.lower()}.github.io/{name}"
    return ""


def push_bark(payload):
    endpoint = os.environ.get("BARK_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("缺少环境变量 BARK_ENDPOINT")
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(endpoint)
    segs = [s for s in parts.path.split("/") if s]
    key = segs[0] if segs else ""
    base = urlunsplit((parts.scheme or "https", parts.netloc or "api.day.app", f"/{key}", "", ""))
    r = requests.post(base, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("code") not in (200, None):
        raise RuntimeError(f"Bark 返回错误：{data}")
    return data


def assign_ids(questions, date_str):
    counters = {}
    for q in questions:
        t = q["topic"]
        counters[t] = counters.get(t, 0) + 1
        q["id"] = f"{t}-{date_str.replace('-', '')}-{counters[t]:02d}"
    return questions


def stub_questions(date_str):
    """本地预览：不调 LLM，用占位内容验证页面结构。"""
    base = [
        {
            "topic": "agent", "difficulty": "资深", "tags": ["tool calling", "幂等"],
            "title": "工具调用超时重试后，Agent 把一个退款执行了两次，如何设计才安全？",
            "why": "LLM 生成的重试策略默认假设工具调用是幂等的，但支付、退款、发消息这类副作用操作并非如此；超时后盲目重试会造成重复扣款或重复通知。",
            "how": ["为每个工具定义幂等键（业务主键 + 操作类型），由服务端去重", "把超时、连接失败与业务失败区分开，只对可安全重试的错误自动重试", "在 Agent 编排层记录调用意图与结果，失败重试前先查询执行状态", "对外部系统提供补偿接口，避免依赖模型自行纠错"],
            "code": "def call_refund(order_id: str, idem_key: str):\n    resp = client.post('/refunds', json={'order_id': order_id},\n                      headers={'Idempotency-Key': idem_key}, timeout=5)\n    return resp.json()",
            "scenario": "某项目在 Agent 中加入 3 次自动重试后，退款接口 P99 上升到 8 秒，且出现重复退款工单；排查发现超时发生在服务端已执行、响应丢失的窗口。",
            "followups": [
                {"q": "幂等键应该由谁生成、保存多久？", "a": "由业务侧生成并持久化，保留时间要覆盖最大重试窗口与对账周期；Agent 只传递，不自行生成。"},
                {"q": "无法改造外部接口时怎么办？", "a": "在适配层做状态查询 + 去重表，或把操作改成两阶段提交/异步确认。"},
            ],
            "diagram": "sequenceDiagram\n  participant U as 用户\n  participant A as Agent\n  participant S as 退款服务\n  U->>A: 申请退款\n  A->>S: POST /refunds (Idempotency-Key)\n  S-->>A: 超时\n  A->>S: 重试（同一幂等键）\n  S-->>A: 返回首次结果",
            "source_type": "", "source_url": "", "source_excerpt": "",
        },
        {
            "topic": "agent", "difficulty": "进阶", "tags": ["memory", "上下文"],
            "title": "多轮对话中 Agent 记忆越用越乱，上下文应该怎么分层？",
            "why": "把所有历史消息塞进上下文会稀释注意力并推高成本，而过度摘要又丢失关键约束，导致前后回答矛盾。",
            "how": ["把记忆分为会话内、任务内与长期三类，分别设定保留策略", "任务内用结构化状态（目标、约束、已完成步骤）替代原始消息", "长期记忆写入前做抽取与去重，读取时按相关性检索", "每次调用前按 token 预算裁剪并保留最近关键约束"],
            "code": "",
            "scenario": "某客服 Agent 在第 8 轮后开始重复询问已提供的订单号；日志显示摘要策略丢掉了实体字段，但保留了寒暄内容。",
            "followups": [
                {"q": "摘要和检索怎么配合？", "a": "摘要负责稳定事实与约束，检索负责可召回的长尾细节，两者写入同一任务状态。"},
            ],
            "diagram": "",
            "source_type": "", "source_url": "", "source_excerpt": "",
        },
        {
            "topic": "rag", "difficulty": "资深", "tags": ["chunking", "召回"],
            "title": "文档切块后召回率不升反降，chunk 策略该怎么诊断？",
            "why": "固定长度切块会把定义与条件拆散，embedding 只截取到半句话；同时块过大导致噪声向量，过小又丢失上下文。",
            "how": ["先抽样标注一批问题与正确片段，建立召回基线", "对比固定长度、按标题层级、语义切块的命中率与 token 成本", "为块补充标题路径与元数据，并保留相邻块用于扩展", "对边界案例做 overlap 与小标题切分"],
            "code": "",
            "scenario": "某知识库把 chunk_size 从 512 调到 256 后，Top-5 召回率下降 12%；分析发现产品手册的表格与步骤被切断，回答开始拼凑不完整步骤。",
            "followups": [
                {"q": "overlap 设多少合适？", "a": "没有固定值，需按文档结构与评测集调参；overlap 过大只是用成本换召回。"},
            ],
            "diagram": "flowchart TD\n  A[原始文档] --> B[按标题层级切块]\n  B --> C[补充标题路径元数据]\n  C --> D[向量化并入库]\n  D --> E[检索命中并扩展相邻块]",
            "source_type": "", "source_url": "", "source_excerpt": "",
        },
        {
            "topic": "rag", "difficulty": "进阶", "tags": ["rerank", "延迟"],
            "title": "加上 rerank 后准确率提升但延迟超标，怎么取舍？",
            "why": "交叉编码器精度高但计算量随候选数线性增长，直接对 Top-50 重排会让首字延迟翻倍。",
            "how": ["缩小初筛候选集并提高召回质量", "选择轻量 rerank 模型或蒸馏版本", "把重排做成可降级的异步步骤", "按业务场景分级：问答可容忍延迟，搜索联想不行"],
            "code": "",
            "scenario": "某 RAG 服务接入 rerank 后 Top-1 命中率提升 9%，但 P95 延迟从 900ms 涨到 2.3s，移动端用户明显流失。",
            "followups": [{"q": "如何评估 rerank 是否值得？", "a": "用离线评测看命中提升，用线上分桶看留存与延迟曲线，算单位延迟的收益。"}],
            "diagram": "",
            "source_type": "", "source_url": "", "source_excerpt": "",
        },
        {
            "topic": "fastapi", "difficulty": "资深", "tags": ["依赖注入", "测试"],
            "title": "FastAPI 依赖注入在测试里为什么总被真实连接池拖垮？",
            "why": "路由依赖在应用启动时就构建了真实资源，测试若只覆盖请求层，会把数据库、模型客户端一并拉起，导致慢与不稳定。",
            "how": ["把外部资源封装成 lifespan 管理的单例依赖", "用 app.dependency_overrides 在测试中替换为内存实现", "对 yield 依赖确保 finally 清理，避免连接泄漏", "在 CI 中显式断言测试未触达真实网路"],
            "code": "def get_db():\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()\n\napp.dependency_overrides[get_db] = lambda: FakeSession()",
            "scenario": "某团队测试套件从 40 秒涨到 6 分钟，原因是每个用例都真实连接了向量库；改用依赖覆盖后恢复到秒级，并消除了偶发超时。",
            "followups": [{"q": "dependency_overrides 的清理时机？", "a": "用 fixture 在用例结束后清空覆盖表，避免污染其他测试。"}],
            "diagram": "",
            "source_type": "", "source_url": "", "source_excerpt": "",
        },
        {
            "topic": "fastapi", "difficulty": "进阶", "tags": ["流式输出", "SSE"],
            "title": "StreamingResponse 接大模型输出时，为什么客户端总是等很久才看到首字？",
            "why": "服务端缓冲、反向代理聚合与生成器未及时 flush 都会把流式响应变成整块返回。",
            "how": ["确认生成器每次 yield 后立即产生数据", "在响应头禁用缓冲并设置合适的内容类型", "检查 Nginx/网关的 proxy_buffering 配置", "对首字延迟单独埋点，与总耗时区分"],
            "code": "",
            "scenario": "某问答接口本地测试流式正常，上线后首字延迟 4 秒；定位为网关开启了响应缓冲，关闭后恢复到 300ms 内。",
            "followups": [{"q": "如何处理中途断流？", "a": "客户端根据 SSE 事件序号续传，服务端保留短期状态或从断点重建。"}],
            "diagram": "",
            "source_type": "", "source_url": "", "source_excerpt": "",
        },
    ]
    return assign_ids(base, date_str)


def main(argv=None):
    ap = argparse.ArgumentParser(description="每日 AI 面试题")
    ap.add_argument("--dry-run", action="store_true", help="不调 LLM、不写题库、不推送")
    ap.add_argument("--fetch-only", action="store_true", help="只抓取线索并输出摘要")
    ap.add_argument("--no-push", action="store_true", help="不推送 Bark")
    ap.add_argument("--date", help="日期 YYYY-MM-DD，默认今天（北京时间）")
    args = ap.parse_args(argv)

    date_str = args.date or datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d")
    DATA.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    BANK.mkdir(exist_ok=True)

    seeds = sources.sync_seeds(DATA)
    issues = sources.fetch_issues()
    web = sources.fetch_web_clues()

    index = bank.load_index(BANK)

    if args.fetch_only:
        clue_sets = {
            t: sources.pick_clues(DATA, seeds, t, date_str, persist=False)
            for t in config.TOPIC_ORDER
        }
        issue_pick = sources.pick_issues(DATA, issues, date_str, persist=False)
        out = DATA / f"sources_{date_str}.json"
        out.write_text(json.dumps(
            {"clues": clue_sets, "issues": issue_pick, "web": web},
            ensure_ascii=False, indent=1,
        ), encoding="utf-8")
        print(f"[fetch-only] 线索已写入 {out}；issue {len(issue_pick)}，社区 {len(web)}")
        return 0

    note = ""
    if args.dry_run:
        questions = stub_questions(date_str)
        note = "预览模式：未调用 DeepSeek，题目为占位示例。"
    else:
        clue_sets = {
            t: sources.pick_clues(DATA, seeds, t, date_str)
            for t in config.TOPIC_ORDER
        }
        issue_pick = sources.pick_issues(DATA, issues, date_str)
        questions, generated = [], []
        for topic in config.TOPIC_ORDER:
            try:
                qs = generate.generate_topic(
                    topic, config.TOPIC_QUOTA[topic], clue_sets[topic],
                    issue_pick, web, index, [q["title"] for q in generated],
                )
            except Exception as exc:
                print(f"[warn] {config.TOPIC_NAMES[topic]} 生成失败：{exc}")
                qs = []
            print(f"[gen] {config.TOPIC_NAMES[topic]}：{len(qs)} 道")
            questions.extend(qs)
            generated.extend(qs)
        if not questions:
            raise RuntimeError("今日生成 0 道题，检查数据源与模型日志")
        questions = generate.dedupe_questions(questions, index)
        generate.validate_diagrams(questions)
        assign_ids(questions, date_str)
        if len(questions) < config.DAILY_TOTAL:
            note = f"今日素材不足，仅 {len(questions)} 道达到标准。"

    if not args.dry_run and questions:
        entries = []
        for q in questions:
            seq = int(q["id"].split("-")[-1])
            qid, path = bank.write_question(BANK, q, date_str, seq)
            entries.append(bank.index_entry(q, qid, path, date_str))
        bank.append_to_index(index, entries, date_str)
        bank.save_index(BANK, index)
        print(f"[bank] 新增 {len(entries)} 道，题库共 {len(index['questions'])} 道")

    archive = sorted(
        set(f.stem for f in DOCS.glob("*.html") if f.stem != "index") | {date_str},
        reverse=True,
    )
    page = render.build_daily_page(questions, date_str, note, archive)
    (DOCS / f"{date_str}.html").write_text(page, encoding="utf-8")
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / "bank").mkdir(exist_ok=True)
    (DOCS / "bank" / "index.html").write_text(render.build_bank_page(index, date_str), encoding="utf-8")

    (DATA / "last_questions.json").write_text(json.dumps(
        {"date": date_str, "note": note, "questions": questions},
        ensure_ascii=False, indent=1,
    ), encoding="utf-8")

    base = page_base()
    url = f"{base}/{date_str}.html" if base else ""
    pushed = False
    if args.dry_run or args.no_push:
        print("[push] 跳过（dry-run / no-push）")
    else:
        payload = render.build_bark_payload(questions, date_str, url, note)
        resp = push_bark(payload)
        pushed = True
        print(f"[push] Bark OK：{resp}")

    (DATA / "last_run.json").write_text(json.dumps({
        "date": date_str,
        "questions": len(questions),
        "note": note,
        "pushed": pushed,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[done] {date_str}: {len(questions)} 道，页面 docs/{date_str}.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
