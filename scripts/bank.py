# -*- coding: utf-8 -*-
"""全局题库：Markdown 存储、索引、相似度去重。"""

import difflib
import json
import re
from datetime import datetime
from pathlib import Path


def norm(text):
    return re.sub(r"[^\w一-鿿]+", "", (text or "").lower())


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def load_index(bank_dir):
    path = Path(bank_dir) / "index.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            return data
    except Exception:
        pass
    return {"updated": "", "questions": []}


def save_index(bank_dir, index):
    path = Path(bank_dir) / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


def suspects(index, title, topic, threshold):
    out = []
    for q in index.get("questions", []):
        if q.get("topic") != topic:
            continue
        s = sim(title, q.get("title", ""))
        if s >= threshold:
            out.append((q, s))
    out.sort(key=lambda x: -x[1])
    return out


def _md_escape(value):
    return json.dumps(str(value), ensure_ascii=False)


def _to_markdown(q, qid, date):
    tags = q.get("tags") or []
    lines = [
        "---",
        f"id: {qid}",
        f"title: {_md_escape(q['title'])}",
        f"topic: {q['topic']}",
        f"difficulty: {q.get('difficulty', '进阶')}",
        f"tags: {json.dumps(tags, ensure_ascii=False)}",
        f"date: {date}",
        f"source_type: {q.get('source_type', '')}",
        f"source_url: {_md_escape(q.get('source_url', ''))}",
        f"source_excerpt: {_md_escape(q.get('source_excerpt', ''))}",
        f"diagram: {'true' if q.get('diagram') else 'false'}",
        "---",
        "",
        f"# {q['title']}",
        "",
        "## 为什么会有这个问题",
        "",
        q.get("why", ""),
        "",
        "## 怎么做",
        "",
    ]
    for i, step in enumerate(q.get("how") or [], 1):
        lines.append(f"{i}. {step}")
    if q.get("code"):
        lines += ["", "## 关键代码", "", "```python", q["code"].rstrip(), "```"]
    lines += ["", "## 真实场景", "", q.get("scenario", "")]
    if q.get("diagram"):
        lines += ["", "## 示意图", "", "```mermaid", q["diagram"].rstrip(), "```"]
    if q.get("followups"):
        lines += ["", "## 面试官追问", ""]
        for i, f in enumerate(q["followups"], 1):
            lines += [f"{i}. **Q：** {f.get('q', '')}", "", f"   **A：** {f.get('a', '')}", ""]
    if q.get("source_url"):
        lines += ["", f"来源：{q['source_url']}"]
    return "\n".join(lines).rstrip() + "\n"


def write_question(bank_dir, q, date, seq):
    topic = q["topic"]
    qid = f"{topic}-{date.replace('-', '')}-{seq:02d}"
    folder = Path(bank_dir) / topic
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{qid}.md"
    path.write_text(_to_markdown(q, qid, date), encoding="utf-8")
    return qid, str(path.relative_to(Path(bank_dir)))


def index_entry(q, qid, path, date):
    return {
        "id": qid,
        "title": q["title"],
        "topic": q["topic"],
        "difficulty": q.get("difficulty", "进阶"),
        "tags": q.get("tags") or [],
        "date": date,
        "source_type": q.get("source_type", ""),
        "source_url": q.get("source_url", ""),
        "path": path,
        "has_diagram": bool(q.get("diagram")),
    }


def append_to_index(index, entries, date):
    index.setdefault("questions", []).extend(entries)
    index["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return index
