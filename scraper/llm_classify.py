"""
Option C — optional Claude classification (highest accuracy).

Runs ONLY when the environment variable ANTHROPIC_API_KEY is set (in GitHub:
Settings -> Secrets and variables -> Actions -> New repository secret).
Without it, this module does nothing and costs nothing.

Each event is classified once: results are cached in
scraper/cache/llm_labels.json (committed by the Action), keyed by a hash of
title + description, so the daily run only sends events it has never seen.
MAX_NEW_PER_RUN bounds the worst-case spend of a single run.
"""

import hashlib
import json
import os
import re

import requests

import taxonomy as T

API = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("EH_LLM_MODEL", "claude-haiku-4-5-20251001")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "llm_labels.json")
BATCH = 20
MAX_NEW_PER_RUN = int(os.environ.get("EH_LLM_MAX_NEW", "300"))

PROFILE = """The reader is a 2nd-year PhD student at IISc Bengaluru (Joint Astronomy
and Astrophysics Programme). Research: cosmology — dark energy reconstruction with
neural networks, simulation-based inference with DESI/Pantheon+ data, phantom
crossing. Strong interests: all of cosmology (top priority), AI/ML theory and ML
for science, astrophysics, and pure mathematics (number theory, topology, algebra,
geometry, probability). Moderately interested in GR, high-energy theory and
mathematical physics. Not interested in engineering, biology, chemistry,
humanities or administrative events."""


def _key(ev):
    s = (ev.get("title") or "") + "|" + (ev.get("description") or "")[:300]
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def _load():
    try:
        with open(CACHE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(cache):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w") as f:
        json.dump(cache, f, indent=0, sort_keys=True)


def _prompt(batch):
    sub = "\n".join(f"- {sf}: {v[1]}" for sf, v in T.SUBFIELDS.items())
    items = "\n".join(
        f'{i}. TITLE: {e.get("title","")}\n   TYPE: {e.get("type","")}\n'
        f'   DESCRIPTION: {(e.get("description") or "")[:500]}'
        for i, e in enumerate(batch))
    return f"""{PROFILE}

Classify each academic event below. Allowed sub-field ids:
{sub}

For each event return:
- "subfields": the sub-field ids it is genuinely about (0-3, most specific first;
  [] if it matches none — e.g. biology, engineering, admin, public outreach unrelated
  to these fields)
- "relevance": 0-100, how worthwhile this event is for the reader above
- "reason": at most 12 words

Events:
{items}

Respond with ONLY a JSON array of {len(batch)} objects in the same order,
each {{"i": <index>, "subfields": [...], "relevance": <int>, "reason": "..."}}.
No prose, no markdown fences."""


def _call(batch, key):
    r = requests.post(API, timeout=120, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01",
        "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 4000,
              "messages": [{"role": "user", "content": _prompt(batch)}]})
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", [])
                   if b.get("type") == "text")
    text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
    arr = json.loads(text)
    out = {}
    for obj in arr:
        i = obj.get("i")
        if isinstance(i, int) and 0 <= i < len(batch):
            out[i] = {"subfields": [s for s in obj.get("subfields", []) if s in T.SUBFIELDS],
                      "relevance": int(obj.get("relevance", 0)),
                      "reason": str(obj.get("reason", ""))[:120],
                      "model": MODEL}
    return out


def classify_all(events):
    """-> (list aligned with events of dict|None, status dict for health)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    cache = _load()
    keys = [_key(e) for e in events]
    if not key:
        # still use cached labels from earlier runs, if any
        hits = sum(k in cache for k in keys)
        return [cache.get(k) for k in keys], {
            "status": "off", "detail": f"no ANTHROPIC_API_KEY; {hits} cached labels reused"}
    todo = [i for i, k in enumerate(keys) if k not in cache][:MAX_NEW_PER_RUN]
    done, errors = 0, 0
    for s in range(0, len(todo), BATCH):
        idx = todo[s:s + BATCH]
        try:
            res = _call([events[i] for i in idx], key)
        except Exception as exc:
            errors += 1
            print(f"  [llm] batch failed: {exc}")
            if errors >= 3:
                break
            continue
        for j, i in enumerate(idx):
            if j in res:
                cache[keys[i]] = res[j]
                done += 1
    _save(cache)
    pending = sum(k not in cache for k in keys)
    return [cache.get(k) for k in keys], {
        "status": "on" if errors < 3 else "degraded",
        "detail": f"model {MODEL}; {done} newly classified, {pending} pending, "
                  f"{len(cache)} cached; {errors} failed batches"}
