# -*- coding: utf-8 -*-
"""题目生成：按主题分批调用 reasoner，校验结构，去重复核，Mermaid 语法门禁。"""

import json
import os
import re
import subprocess

from . import bank, config, llm

SYSTEM_PROMPT = """你是 AI 应用方向（Agent / RAG / FastAPI）的资深面试官与面试辅导专家。目标候选人：3–5 年经验的应用开发，中高级。

你要出「真实工程问题驱动」的面试题，并给出结构化答案。硬性要求：
1. 题目来自真实痛点：现实中会出现的故障、瓶颈、选型取舍；不考名词定义，不背八股。
2. 每题答案结构固定：
   - why：这个问题为什么存在（工程背景、原理、常见错误认知）
   - how：可落地的解决步骤（分步，含关键配置或伪代码）
   - scenario：真实工程场景（具体症状、指标、排查路径）；不编造公司名与具体数值，用「某项目 / 典型现象」表述
   - followups：1–2 个面试官追问与回答要点
3. 中高级难度：考察边界条件、成本与性能取舍、故障定位。
4. 题面中文，技术术语保留英文；difficulty 只取「进阶」或「资深」。
5. 代码只用 Python，关键片段 ≤ 40 行，可直接展示，不要堆注释。
6. diagram 可选：只有确实帮助理解的题才给，必须是合法 Mermaid，以 flowchart TD 或 sequenceDiagram 开头，节点文字用中文，避免特殊符号。
7. 不得抄袭线索原文；题目与答案必须原创改写。
8. 只输出 JSON，不要任何解释或代码块围栏。

输出结构：
{"questions":[{"title":"","topic":"agent|rag|fastapi","difficulty":"进阶|资深","tags":["2-4 个"],"why":"","how":["步骤1","步骤2","步骤3"],"code":"","scenario":"","followups":[{"q":"","a":""}],"diagram":"","source_type":"面经|issue|文档","source_url":"取自已提供线索的 url，没有就空字符串","source_excerpt":"若来自面经线索，用 ≤120 字原创概括原考点"}]}"""

JUDGE_PROMPT = """你是面试题库的查重编辑。给你若干「新题 / 旧题」标题对，判断它们是否是同一个核心问题（即使换了说法或换了技术版本）。只输出 JSON：{"duplicates":[重复的对的编号列表]}，编号从 0 开始。"""


def _clue_lines(clues):
    return "\n".join(f"- [{c['topic']}] {c['title']}（{c['url']}）" for c in clues) or "-（无）"


def _issue_lines(issues):
    out = []
    for x in issues:
        out.append(f"- {x['repo']} | {x['title']} | {x.get('excerpt', '')[:350]}（{x['url']}）")
    return "\n".join(out) or "-（无）"


def _web_lines(web):
    return "\n".join(f"- {w['source']}：{w['title']}" for w in web) or "-（无）"


def _doc_lines():
    return "\n".join(f"- {t}" for t in config.FASTAPI_TOPICS) or "-（无）"


def build_user_prompt(topic, quota, clues, issues, web, bank_titles, generated_titles):
    name = config.TOPIC_NAMES[topic]
    parts = [
        f"请出 {quota} 道 {name} 方向面试题（中高级，面向 3–5 年应用开发）。",
        "",
        "【面经考点线索】（只作灵感，禁止照抄题面或答案）",
        _clue_lines(clues),
        "",
        "【真实 issue 场景】（可改写成题，source_type=issue，source_url 用原 url；只选应用层可迁移的问题，忽略底层实现细节）",
        _issue_lines(issues) if topic in ("agent", "rag") else "-（无）",
        "",
        "【近期社区讨论】（仅参考）",
        _web_lines(web),
        "",
    ]
    if topic == "fastapi":
        parts += ["【官方文档考点】", _doc_lines(), ""]
    parts += [
        "【已有题库标题】（禁止重复或近义重复）",
        "\n".join(f"- {t}" for t in bank_titles) or "-（无）",
        "",
        "【本批次已生成标题】（不得重复）",
        "\n".join(f"- {t}" for t in generated_titles) or "-（无）",
        "",
        "请输出 JSON。",
    ]
    return "\n".join(parts)


def generate_topic(topic, quota, clues, issues, web, index, generated_titles):
    """按每批 2 道分批生成；reasoner 的思考 token 会挤占输出额度，小批次更稳。"""
    bank_titles = [
        q["title"] for q in index.get("questions", [])
        if q.get("topic") == topic
    ][-150:]
    allowed = {c["url"] for c in clues} | {x["url"] for x in issues} | {w["url"] for w in web}
    out, attempts = [], 0
    while len(out) < quota and attempts < 5:
        attempts += 1
        need = min(2, quota - len(out))
        titles = list(generated_titles) + [q["title"] for q in out]
        user = build_user_prompt(topic, need, clues, issues, web, bank_titles, titles)
        try:
            data = llm.reasoner(SYSTEM_PROMPT, user)
        except Exception as exc:
            print(f"[warn] {topic} 批次生成失败：{exc}")
            break
        qs = validate_questions(data.get("questions") or [], topic, allowed, need)
        if not qs:
            break
        out.extend(qs)
    return out[:quota]


def validate_questions(raw, topic, allowed_urls, quota):
    out = []
    for q in raw:
        if not isinstance(q, dict):
            continue
        title = str(q.get("title") or "").strip()
        why = str(q.get("why") or "").strip()
        how = [str(x).strip() for x in (q.get("how") or []) if str(x).strip()]
        scenario = str(q.get("scenario") or "").strip()
        followups = []
        for f in q.get("followups") or []:
            if isinstance(f, dict) and str(f.get("q") or "").strip() and str(f.get("a") or "").strip():
                followups.append({"q": str(f["q"]).strip(), "a": str(f["a"]).strip()})
        if not (8 <= len(title) <= 90) or len(why) < 40 or len(how) < 3:
            print(f"[warn] 淘汰字段不全的题：{title[:40]}")
            continue
        if len(scenario) < 50 or not followups:
            print(f"[warn] 淘汰场景/追问不足的题：{title[:40]}")
            continue
        tags = [str(t).strip() for t in (q.get("tags") or []) if str(t).strip()][:5]
        url = str(q.get("source_url") or "").strip()
        if url not in allowed_urls:
            url = ""
        diagram = str(q.get("diagram") or "").strip()
        if diagram and not re.match(r"^(flowchart|graph|sequenceDiagram)\b", diagram):
            diagram = ""
        source_type = str(q.get("source_type") or "").strip()
        if source_type not in ("面经", "issue", "文档"):
            source_type = "面经" if url else ""
        code = str(q.get("code") or "").strip()
        code = re.sub(r"^```[a-zA-Z]*\s*", "", code)
        code = re.sub(r"\s*```$", "", code)
        out.append({
            "title": title,
            "topic": topic,
            "difficulty": "资深" if str(q.get("difficulty")) == "资深" else "进阶",
            "tags": tags,
            "why": why,
            "how": how,
            "code": code,
            "scenario": scenario,
            "followups": followups,
            "diagram": diagram,
            "source_type": source_type,
            "source_url": url,
            "source_excerpt": str(q.get("source_excerpt") or "").strip()[:200],
        })
        if len(out) >= quota:
            break
    return out


def dedupe_questions(questions, index):
    threshold = config.DEDUPE_SIM
    accepted, pending = [], []
    for q in questions:
        dups = [x["title"] for x, _ in bank.suspects(index, q["title"], q["topic"], threshold)]
        for a in accepted:
            if a["topic"] == q["topic"] and bank.sim(q["title"], a["title"]) >= threshold:
                dups.append(a["title"])
        if dups:
            pending.append((q, dups[:3]))
        else:
            accepted.append(q)
    if not pending:
        return accepted

    pairs = [{"new": q["title"], "old": old} for q, olds in pending for old in olds]
    try:
        verdict = llm.judge(JUDGE_PROMPT, json.dumps({"pairs": pairs}, ensure_ascii=False))
        dup_idx = set(int(i) for i in (verdict.get("duplicates") or []))
    except Exception as exc:
        print(f"[warn] 去重复核失败，保守丢弃疑似题：{exc}")
        dup_idx = set(range(len(pairs)))

    cursor = 0
    for q, olds in pending:
        is_dup = any(i in dup_idx for i in range(cursor, cursor + len(olds)))
        cursor += len(olds)
        if is_dup:
            print(f"[dedupe] 丢弃近似题：{q['title'][:44]}")
        else:
            accepted.append(q)
    return accepted


def validate_diagrams(questions):
    if not os.environ.get("MERMAID_CHECK"):
        return
    diagrams = [q["diagram"] for q in questions if q.get("diagram")]
    if not diagrams:
        return
    try:
        proc = subprocess.run(
            ["node", "scripts/validate_mermaid.mjs"],
            input=json.dumps({"diagrams": diagrams}),
            capture_output=True, text=True, timeout=180,
        )
        results = json.loads(proc.stdout.strip().splitlines()[-1])["results"]
    except Exception as exc:
        print(f"[warn] Mermaid 校验不可用，保留原图：{exc}")
        return
    i = 0
    for q in questions:
        if q.get("diagram"):
            if i < len(results) and not results[i]:
                print(f"[warn] Mermaid 语法无效，去掉图：{q['title'][:40]}")
                q["diagram"] = ""
            i += 1
