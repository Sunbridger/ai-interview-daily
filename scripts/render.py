# -*- coding: utf-8 -*-
"""渲染：公众号风格每日页、题库索引页、Bark 通知。"""

import html
import json
from datetime import date

from . import config

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#fff;color:#3f3f3f;font:16px/1.9 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;letter-spacing:.4px;-webkit-font-smoothing:antialiased}
main{width:80%;max-width:1080px;margin:0 auto;padding:44px 0 80px}
.masthead{text-align:center}
.kicker{display:inline-block;font-size:12px;letter-spacing:2px;color:#d4472a;border:1px solid #f0cfc6;background:#fdf5f2;padding:3px 12px;border-radius:2px}
h1{font-size:24px;line-height:1.5;color:#1a1a1a;font-weight:700;margin:18px 0 6px}
.masthead .meta{font-size:13px;color:#999;margin:0}
.lede{font-size:15px;color:#8a8a8a;text-align:center;margin:14px 0 0}
.orn{display:flex;align-items:center;gap:12px;margin:30px 0;color:#d8d8d8;font-size:10px;line-height:1}
.orn:before,.orn:after{content:"";flex:1;height:1px;background:#eee}
.topic-head{text-align:center;margin:46px 0 6px}
.topic-head span{display:inline-block;font:600 13px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.22em;color:#d4472a;border-top:1px solid #f0cfc6;border-bottom:1px solid #f0cfc6;padding:7px 16px}
.q{margin:34px 0 0}
.no{display:inline-block;background:#d4472a;color:#fff;font-size:12px;font-weight:600;line-height:1;padding:5px 8px;border-radius:3px;margin-right:9px;vertical-align:3px;letter-spacing:1px}
h2{font-size:19px;line-height:1.65;color:#1a1a1a;font-weight:700;margin:0 0 8px}
.meta-line{font-size:13px;color:#9b9b9b;margin:0 0 16px;padding-left:2px}
.meta-line a{color:#576b95;text-decoration:none}
.tag{display:inline-block;border:1px solid #ececec;border-radius:2px;padding:0 6px;margin-right:5px;font-size:12px;color:#8a8a8a;line-height:1.9}
p{margin:14px 0}
.sub{font-size:15px;font-weight:700;color:#222;margin:24px 0 10px;padding-left:9px;border-left:3px solid #d4472a;line-height:1.5}
.steps{list-style:none;margin:0;padding:0;counter-reset:s}
.steps li{counter-increment:s;position:relative;padding-left:27px;margin:8px 0}
.steps li:before{content:counter(s);position:absolute;left:0;top:0;color:#d4472a;font-weight:600;font-size:14px;line-height:1.9}
.code{background:#f7f7f7;border-radius:4px;padding:14px 16px;margin:16px 0;overflow:auto}
.code code{display:block;font:13px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#2f2f2f;white-space:pre}
.qa{background:#fbfbfb;border-radius:4px;padding:12px 16px;margin:0}
.qa p{margin:6px 0;font-size:15px;color:#444}
.qa strong{color:#1a1a1a}
.diagram{background:#fbfbfb;border:1px solid #eee;border-radius:4px;padding:12px;margin:16px 0;overflow:auto}
.diagram .mermaid{display:flex;justify-content:center}
footer{margin-top:56px;text-align:center;color:#b0b0b0;font-size:12px;line-height:2.2}
footer a{color:#8a9bbf;text-decoration:none}
.empty{text-align:center;color:#9b9b9b;padding:48px 0}
/* 题库页 */
.search-box{margin:32px 0 0}
input[type=search]{width:100%;padding:11px 14px;border:1px solid #e5e5e5;border-radius:4px;font-size:15px;color:#333;outline:none;background:#fff}
input[type=search]:focus{border-color:#d4472a}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 10px}
.filter{border:1px solid #e5e5e5;border-radius:999px;padding:3px 12px;font-size:13px;color:#666;background:#fff;cursor:pointer;font-family:inherit}
.filter.on{border-color:#d4472a;color:#d4472a;background:#fdf5f2}
.count{color:#9b9b9b;font-size:13px;margin:6px 0 14px}
.bank-item{border-top:1px solid #eee;padding:16px 0}
.bank-item a{color:#1a1a1a;text-decoration:none;font-weight:600}
.bank-item a:hover{color:#d4472a}
.bank-item .meta{font-size:12px;color:#9b9b9b;margin-top:4px}
@media (max-width:760px){main{width:auto;padding:32px 20px 64px}}
@media (min-width:1200px){body{font-size:17px}h1{font-size:28px}h2{font-size:21px}.qa p{font-size:16px}}
"""


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _pretty_date(d):
    dt = date.fromisoformat(d)
    wd = "一二三四五六日"[dt.weekday()]
    return f"{dt.month} 月 {dt.day} 日 · 周{wd}"


def _archive_html(archive, current):
    days = [d for d in archive if d != current][:14]
    if not days:
        return ""
    links = " ｜ ".join(f'<a href="{_esc(d)}.html">{_esc(d[5:])}</a>' for d in days)
    return f"<p>往期：{links} ｜ <a href=\"bank/index.html\">题库</a></p>"


def _topic_counts(questions):
    counts = {}
    for q in questions:
        counts[q["topic"]] = counts.get(q["topic"], 0) + 1
    return " · ".join(
        f"{config.TOPIC_NAMES[t]} {counts.get(t, 0)}"
        for t in config.TOPIC_ORDER
    )


def _question_html(i, q):
    qid = q.get("id") or f"q{i}"
    tags = "".join(f'<span class="tag">{_esc(t)}</span>' for t in (q.get("tags") or []))
    src = ""
    if q.get("source_url"):
        label = q.get("source_type") or "来源"
        src = f' ｜ <a href="{_esc(q["source_url"])}" target="_blank" rel="noopener">{_esc(label)}来源 ↗</a>'
    parts = [
        f'<section class="q" id="{_esc(qid)}">',
        f'<h2><span class="no">{i:02d}</span>{_esc(q["title"])}</h2>',
        f'<p class="meta-line">{_esc(q.get("difficulty", "进阶"))} ｜ {tags}{src}</p>',
    ]
    if q.get("why"):
        parts.append(f'<p class="sub">为什么会有这个问题</p><p>{_esc(q["why"])}</p>')
    if q.get("how"):
        steps = "".join(f"<li>{_esc(s)}</li>" for s in q["how"])
        parts.append(f'<p class="sub">怎么做</p><ol class="steps">{steps}</ol>')
    if q.get("code"):
        parts.append(f'<div class="code"><code>{_esc(q["code"])}</code></div>')
    if q.get("scenario"):
        parts.append(f'<p class="sub">真实场景</p><p>{_esc(q["scenario"])}</p>')
    if q.get("diagram"):
        parts.append(
            f'<div class="diagram"><pre class="mermaid">{_esc(q["diagram"])}</pre></div>'
        )
    if q.get("followups"):
        qa = "".join(
            f"<p><strong>Q：</strong>{_esc(f.get('q', ''))}</p>"
            f"<p><strong>A：</strong>{_esc(f.get('a', ''))}</p>"
            for f in q["followups"]
        )
        parts.append(f'<p class="sub">面试官追问</p><div class="qa">{qa}</div>')
    parts.append("</section>")
    return "".join(parts)


def build_daily_page(questions, date_str, note="", archive=None):
    archive = archive or []
    dt = date.fromisoformat(date_str)
    groups = []
    number = 0
    for topic in config.TOPIC_ORDER:
        items = [q for q in questions if q["topic"] == topic]
        if not items:
            continue
        groups.append(
            f'<div class="topic-head"><span>{_esc(config.TOPIC_NAMES[topic])} 专题</span></div>'
        )
        for q in items:
            number += 1
            groups.append(_question_html(number, q))
    body = "".join(groups) or '<p class="empty">今天没有达到质量标准的题目。宁缺勿滥，明天见。</p>'
    lede = f'<p class="lede">{_esc(note)}</p>' if note else ""
    has_diagram = any(q.get("diagram") for q in questions)
    mermaid_scripts = ""
    if has_diagram:
        mermaid_scripts = (
            '<script src="vendor/mermaid.min.js"></script>'
            '<script>mermaid.initialize({startOnLoad:true,theme:"neutral",securityLevel:"loose"});</script>'
        )
    footer_archive = _archive_html(archive, date_str)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 面试题日报 · {_esc(date_str)}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<header class="masthead">
<span class="kicker">AI 面试题日报</span>
<h1>{dt.month} 月 {dt.day} 日 · {len(questions)} 道</h1>
<p class="meta">{_esc(date_str)} · 周{"一二三四五六日"[dt.weekday()]} · {_topic_counts(questions)} · 中高级</p>
{lede}
</header>
<div class="orn"><span>◆</span></div>
{body}
<footer>
<p>每天 08:00 更新 ｜ 面向 3–5 年经验的应用开发 ｜ 题目永久去重，持续累积</p>
{footer_archive}
</footer>
</main>
{mermaid_scripts}
</body>
</html>
"""


def build_bank_page(index, date_str):
    questions = index.get("questions", [])
    data = []
    for q in sorted(questions, key=lambda x: (x.get("date", ""), x.get("id", "")), reverse=True):
        data.append({
            "id": q.get("id", ""),
            "title": q.get("title", ""),
            "topic": q.get("topic", ""),
            "topicName": config.TOPIC_NAMES.get(q.get("topic", ""), q.get("topic", "")),
            "difficulty": q.get("difficulty", ""),
            "tags": q.get("tags") or [],
            "date": q.get("date", ""),
            "source_type": q.get("source_type", ""),
            "href": f'../{q.get("date", "")}.html#{q.get("id", "")}',
        })
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 面试题库</title>
<style>{CSS}</style>
</head>
<body>
<main>
<header class="masthead">
<span class="kicker">AI 面试题库</span>
<h1>共 {len(data)} 道题</h1>
<p class="meta">Agent · RAG · FastAPI ｜ 永久去重，每天新增</p>
</header>
<div class="search-box">
<input id="kw" type="search" placeholder="搜索题目关键字或标签，例如：重排、依赖注入、工具调用">
<div class="filters" id="filters"></div>
<p class="count" id="count"></p>
<div id="list"></div>
</div>
<footer>
<p><a href="../index.html">← 返回今日题目</a> ｜ 题库自动维护，点击题目跳转到当日页面</p>
</footer>
</main>
<script id="bank-data" type="application/json">{blob}</script>
<script>
(function(){{
  var data = JSON.parse(document.getElementById("bank-data").textContent);
  var state = {{topic:"all", diff:"all", source:"all", kw:""}};
  var filtersEl = document.getElementById("filters");
  var listEl = document.getElementById("list");
  var countEl = document.getElementById("count");
  var kwEl = document.getElementById("kw");

  function makeFilter(label, value, key){{
    var b = document.createElement("button");
    b.className = "filter" + (state[key] === value ? " on" : "");
    b.textContent = label;
    b.onclick = function(){{ state[key] = value; draw(); }};
    return b;
  }}
  function drawFilters(){{
    filtersEl.textContent = "";
    [["全部主题","all","topic"],["Agent","agent","topic"],["RAG","rag","topic"],["FastAPI","fastapi","topic"]]
      .forEach(function(f){{ filtersEl.appendChild(makeFilter(f[0], f[1], f[2])); }});
    [["全部难度","all","diff"],["进阶","进阶","diff"],["资深","资深","diff"]]
      .forEach(function(f){{ filtersEl.appendChild(makeFilter(f[0], f[1], f[2])); }});
    [["全部来源","all","source"],["面经","面经","source"],["issue","issue","source"],["文档","文档","source"]]
      .forEach(function(f){{ filtersEl.appendChild(makeFilter(f[0], f[1], f[2])); }});
  }}
  function match(q){{
    if (state.topic !== "all" && q.topic !== state.topic) return false;
    if (state.diff !== "all" && q.difficulty !== state.diff) return false;
    if (state.source !== "all" && q.source_type !== state.source) return false;
    if (!state.kw) return true;
    var hay = (q.title + " " + q.tags.join(" ")).toLowerCase();
    return hay.indexOf(state.kw.toLowerCase()) >= 0;
  }}
  function draw(){{
    drawFilters();
    var items = data.filter(match);
    countEl.textContent = "显示 " + items.length + " / " + data.length + " 道";
    listEl.textContent = "";
    items.forEach(function(q){{
      var div = document.createElement("div");
      div.className = "bank-item";
      var a = document.createElement("a");
      a.href = q.href; a.textContent = q.title;
      var meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = q.date + " · " + q.topicName + " · " + q.difficulty +
        (q.source_type ? " · " + q.source_type : "") +
        (q.tags.length ? " · " + q.tags.join(" / ") : "");
      div.appendChild(a); div.appendChild(meta);
      listEl.appendChild(div);
    }});
  }}
  kwEl.addEventListener("input", function(){{ state.kw = kwEl.value.trim(); draw(); }});
  draw();
}})();
</script>
</body>
</html>
"""


def build_bark_payload(questions, date_str, page_url="", note=""):
    title = f"AI 面试题 · {date_str[5:]} · {len(questions)} 道"
    if not questions:
        body = "今日没有达到质量标准的题目。宁缺勿滥，明天见。"
    else:
        lines = [
            f"{i}. [{config.TOPIC_NAMES.get(q['topic'], q['topic'])}] {q['title']}"
            for i, q in enumerate(questions, 1)
        ]
        if len(questions) < config.DAILY_TOTAL:
            lines += ["", f"今日素材不足，仅 {len(questions)} 道。"]
        if note:
            lines += ["", note]
        body = "\n".join(lines)
    payload = {
        "title": title,
        "body": body,
        "group": config.BARK_GROUP,
        "ttl": config.BARK_TTL,
    }
    if page_url:
        payload["url"] = page_url
    return payload
