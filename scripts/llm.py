# -*- coding: utf-8 -*-
"""DeepSeek 调用：reasoner 出题，chat 做去重复核。"""

import json
import os
import re
import time

import requests

API_URL = "https://api.deepseek.com/chat/completions"


def _loads(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        if start < 0:
            raise
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return obj


def _post(model, messages, max_tokens, json_mode=False, temperature=None, timeout=600):
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY")
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if temperature is not None:
        payload["temperature"] = temperature
    last_err = None
    for attempt in (1, 2):
        try:
            r = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return _loads(content)
        except Exception as exc:
            last_err = exc
            print(f"[warn] {model} 调用失败（第 {attempt} 次）：{exc}")
            if attempt == 1:
                time.sleep(8)
    raise RuntimeError(f"{model} 调用失败：{last_err}")


def reasoner(system, user, max_tokens=8000):
    return _post(
        "deepseek-reasoner",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
    )


def judge(system, user, max_tokens=2000):
    return _post(
        "deepseek-chat",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
        json_mode=True,
        temperature=0,
    )
