# -*- coding: utf-8 -*-
"""数据源：GitHub 种子题库线索、issue 场景、社区搜索线索。"""

import json
import os
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, quote_plus

import requests

from . import config

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "application/vnd.github+json"}

TOPIC_PATH_HINTS = {
    "fastapi": ("fastapi", "starlette", "pydantic", "uvicorn"),
    "rag": ("rag", "retriev", "vector", "embedding", "chunk", "rerank", "向量", "检索", "召回"),
    "agent": ("agent", "tool", "mcp", "multi-agent", "智能体", "工具调用", "langgraph"),
}
Q_START = re.compile(
    r"^(什么是|什么情况|为何|为什么|如何|怎么|怎样|能否|是否|区别|对比|解释|实现|设计|优化|排查|定位|处理|解决|选择|评估|哪些|有什么|如何避免)"
)
Q_PREFIX = re.compile(r"^(?:[Qq]\d*|问题\s*\d*|\d+)\s*[、.．:：)）]\s*")
BAD_PATH = re.compile(r"(translations/|README_(EN|ES|ID|JA|KO|PT|ZH-TW|FR|DE|RU)|i18n|\.github/)", re.I)


def _gh_headers():
    h = dict(HEADERS)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(url, timeout=25, headers=None):
    r = requests.get(url, headers=headers or HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def _classify(path, title):
    s = f"{path} {title}".lower()
    for topic in ("fastapi", "rag", "agent"):
        if any(k in s for k in TOPIC_PATH_HINTS[topic]):
            return topic
    return None


def _extract_questions(text):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) > 140 or s.startswith(("```", "|", "![")):
            continue
        if s.startswith("#"):
            h = re.sub(r"[`*]", "", s.lstrip("#").strip())
            h = Q_PREFIX.sub("", h).strip()
            if 8 <= len(h) <= 100 and (h.endswith(("?", "？")) or Q_START.match(h)):
                out.append(h)
        elif re.match(r"^([-*]|\d+[.、)]|[Qq]\d+[:：])\s*", s):
            t = re.sub(r"^([-*]|\d+[.、)]|[Qq]\d+[:：])\s*", "", s).strip()
            t = re.sub(r"[*_`>#]", "", t).strip()
            if 8 <= len(t) <= 100 and t.endswith(("?", "？")):
                out.append(t)
    return out


# ---------------------------------------------------------------- 种子题库

def _seed_path(data_dir):
    return Path(data_dir) / "seed" / "questions.json"


def sync_seeds(data_dir, force=False):
    path = _seed_path(data_dir)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    synced = raw.get("synced", "")
    if not force and synced:
        try:
            age = (datetime.now(timezone.utc).date() - datetime.strptime(synced, "%Y-%m-%d").date()).days
            if age < config.SEED_SYNC_DAYS:
                print(f"[seed] 使用缓存线索 {len(raw.get('questions', []))} 条（{synced} 同步）")
                return raw.get("questions", [])
        except ValueError:
            pass

    clues, seen = [], set()
    for repo in config.SEED_REPOS:
        try:
            meta = _get(f"https://api.github.com/repos/{repo}", headers=_gh_headers()).json()
            branch = meta.get("default_branch", "main")
            tree = _get(
                f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1",
                headers=_gh_headers(),
            ).json().get("tree", [])
        except Exception as exc:
            print(f"[warn] 种子仓库读取失败 {repo}: {exc}")
            continue

        cands = []
        for item in tree:
            p = item.get("path", "")
            if item.get("type") != "blob" or not p.endswith(".md") or BAD_PATH.search(p):
                continue
            size = item.get("size") or 0
            if not (200 <= size <= 400_000):
                continue
            score = sum(
                1 for ks in TOPIC_PATH_HINTS.values() for k in ks if k in p.lower()
            )
            cands.append((score, -size, p))
        cands.sort(reverse=True)

        for _, _, p in cands[: config.SEED_FILES_PER_REPO]:
            raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{quote(p)}"
            try:
                text = _get(raw_url, timeout=30).text
            except Exception as exc:
                print(f"[warn] 种子文件失败 {repo}/{p}: {exc}")
                continue
            for title in _extract_questions(text)[:80]:
                topic = _classify(p, title)
                norm = re.sub(r"\W+", "", title.lower())
                if not topic or not norm or norm in seen:
                    continue
                seen.add(norm)
                clues.append({
                    "title": title,
                    "topic": topic,
                    "repo": repo,
                    "path": p,
                    "url": f"https://github.com/{repo}/blob/{branch}/{quote(p)}",
                })

    random.Random(20261120).shuffle(clues)
    counts, kept = {}, []
    for c in clues:
        if counts.get(c["topic"], 0) >= config.SEED_PER_TOPIC:
            continue
        counts[c["topic"]] = counts.get(c["topic"], 0) + 1
        kept.append(c)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"synced": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "questions": kept},
        ensure_ascii=False, indent=1,
    ), encoding="utf-8")
    print(f"[seed] 同步 {len(kept)} 条线索：{counts}")
    return kept


# ---------------------------------------------------------------- 线索选择

def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _prune_used(used, days):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return {k: v for k, v in used.items() if str(v) >= cutoff}


def pick_clues(data_dir, pool, topic, today, n=None, persist=True):
    n = n or config.SEED_CLUE_COUNT
    path = Path(data_dir) / "seed" / "used_clues.json"
    used = _prune_used(_load_json(path), config.SEED_REUSE_DAYS)
    candidates = [q for q in pool if q.get("topic") == topic]
    fresh = [q for q in candidates if q["url"] not in used] or candidates
    rnd = random.Random(hash(f"{today}-{topic}") & 0xFFFFFFFF)
    rnd.shuffle(fresh)
    picked = fresh[:n]
    if persist:
        for q in picked:
            used[q["url"]] = today
        _save_json(path, used)
    return picked


def pick_issues(data_dir, issues, today, n=None, persist=True):
    n = n or config.ISSUE_CLUE_COUNT
    path = Path(data_dir) / "seed" / "used_issues.json"
    used = _load_json(path)          # issue 用完永久不再用
    fresh = [x for x in issues if x["url"] not in used]
    rnd = random.Random(hash(today) & 0xFFFFFFFF)
    rnd.shuffle(fresh)
    picked = fresh[:n]
    if persist:
        for x in picked:
            used[x["url"]] = today
        _save_json(path, used)
    return picked


# ---------------------------------------------------------------- GitHub issue

def fetch_issues():
    issues = []
    for repo, label in config.ISSUE_REPOS:
        q = f"repo:{repo} label:{label} is:issue is:closed comments:>=2"
        url = (
            "https://api.github.com/search/issues?q=" + quote(q)
            + "&sort=updated&order=desc&per_page=" + str(config.ISSUE_PER_REPO)
        )
        try:
            items = _get(url, headers=_gh_headers()).json().get("items", [])
        except Exception as exc:
            print(f"[warn] issue 搜索失败 {repo}: {exc}")
            continue
        for it in items:
            body = re.sub(r"```.*?```", " ", it.get("body") or "", flags=re.S)
            body = re.sub(r"<[^>]+>", " ", body)
            body = re.sub(r"\s+", " ", body).strip()
            issues.append({
                "repo": repo,
                "title": it.get("title", ""),
                "url": it.get("html_url", ""),
                "labels": [l.get("name") for l in it.get("labels", [])],
                "comments": it.get("comments", 0),
                "excerpt": body[:700],
            })
    print(f"[issue] 获取 {len(issues)} 条已解决 issue")
    return issues


# ---------------------------------------------------------------- 社区线索

def _walk_titles(obj):
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            t = cur.get("title") or cur.get("articleTitle")
            u = cur.get("url") or cur.get("articleUrl")
            if isinstance(t, str) and isinstance(u, str) and u.startswith("http") and len(t) >= 8:
                yield t, u
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def fetch_web_clues(limit=4):
    """掘金 / CSDN / 牛客，低频尝试；失败不影响主流程。"""
    clues = []

    for kw in config.JUEJIN_KEYWORDS:
        try:
            r = requests.post(
                "https://api.juejin.cn/search_api/v1/search",
                headers={"User-Agent": UA, "Content-Type": "application/json"},
                json={"key_word": kw, "id_type": 0, "cursor": "0", "limit": limit, "search_type": 0},
                timeout=15,
            )
            for it in (r.json().get("data") or [])[:limit]:
                info = ((it.get("result_model") or {}).get("article_info") or {})
                if info.get("title") and info.get("article_id"):
                    clues.append({
                        "title": info["title"],
                        "url": f"https://juejin.cn/post/{info['article_id']}",
                        "source": "掘金",
                    })
        except Exception as exc:
            print(f"[warn] 掘金搜索失败 {kw}: {exc}")

    for kw in config.CSDN_KEYWORDS:
        try:
            r = _get(
                "https://so.csdn.net/api/v3/search?q=" + quote_plus(kw) + "&t=all&p=1",
                timeout=15,
            )
            found = list(_walk_titles(r.json()))
            for title, url in found[:limit]:
                clues.append({"title": title, "url": url, "source": "CSDN"})
        except Exception as exc:
            print(f"[warn] CSDN 搜索失败 {kw}: {exc}")

    try:
        r = _get(
            "https://www.nowcoder.com/discuss/experience/json"
            f"?tagId={config.NOWCODER_TAG}&order=3&phaseId=0",
            timeout=15,
        )
        posts = ((r.json().get("data") or {}).get("discussPosts") or [])
        for p in posts[:limit]:
            title = p.get("postTitle") or p.get("title")
            pid = p.get("postId") or p.get("id")
            if title and pid:
                clues.append({
                    "title": title,
                    "url": f"https://www.nowcoder.com/discuss/{pid}",
                    "source": "牛客",
                })
        print(f"[web] 牛客返回 {len(posts)} 条")
    except Exception as exc:
        print(f"[warn] 牛客低频抓取失败: {exc}")

    seen, out = set(), []
    for c in clues:
        if c["title"] in seen:
            continue
        seen.add(c["title"])
        out.append(c)
    print(f"[web] 社区线索 {len(out)} 条")
    return out[:12]
