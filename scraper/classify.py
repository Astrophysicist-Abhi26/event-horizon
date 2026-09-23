"""
Classification and relevance scoring.

Evidence, strongest first:
  1. declared  subject codes the organisers attached (arXiv/INSPIRE/tags)
  2. keywords  word-bounded regex matches in the title (1.0) and
               description (0.5 each, capped at 1.0 per sub-field)
  3. embedding nearest-centroid match from the self-calibrating embedding
               classifier (Option B) — only used when it is confident
  4. llm       optional Claude classification (Option C) — when present it
               decides the sub-fields, unioned with strong declared codes

A sub-field is assigned when its total evidence reaches TAG_THRESHOLD.
General "(other)" sub-fields are fallbacks and are dropped when a specific
sub-field of the same field is present.
"""

from collections import defaultdict

import taxonomy as T

TAG_THRESHOLD = 1.0
TITLE_HIT = 1.0
DESC_HIT = 0.5
DESC_CAP = 1.0
GENERALS = {"cosmo.general", "astro.general", "math.other", "phys.general", "ai.general"}


def keyword_hits(text):
    """Return {subfield: [matched pattern snippets]} for one piece of text."""
    hits = defaultdict(list)
    if not text:
        return hits
    for sf, pats in T.COMPILED.items():
        for p in pats:
            m = p.search(text)
            if m:
                hits[sf].append(m.group(0))
    return hits


def gather_evidence(ev, embed_result=None):
    """ev: normalised event dict with title, description, declared."""
    score = defaultdict(float)
    why = defaultdict(set)

    for code in ev.get("declared") or []:
        for sf, w in T.declared_codes(code):
            score[sf] += w
            why[sf].add("declared")

    for sf, hs in keyword_hits(ev.get("title", "")).items():
        score[sf] += TITLE_HIT
        why[sf].add("keywords")

    desc_hits = keyword_hits((ev.get("description") or "")[:3000])
    for sf, hs in desc_hits.items():
        if "keywords" in why[sf]:
            continue  # title already counted
        score[sf] += min(DESC_CAP, DESC_HIT * len(set(h.lower() for h in hs)))
        why[sf].add("keywords")

    # ML applied to a science: an AI signal + a physical-science signal
    sci = any(score[s] >= TAG_THRESHOLD for s in score
              if T.parent(s) in ("cosmo", "astro", "physics"))
    if score.get("ai.general", 0) >= TAG_THRESHOLD and sci:
        score["ai.science"] += 1.0
        why["ai.science"].add("keywords")

    if embed_result:
        sf, strength = embed_result
        if sf in T.SUBFIELDS:
            score[sf] += strength
            why[sf].add("embedding")
    return score, why


def assign(score, why):
    tagged = {sf for sf, v in score.items() if v >= TAG_THRESHOLD and sf in T.SUBFIELDS}
    for g in GENERALS:
        fam = T.parent(g)
        if g in tagged and any(T.parent(s) == fam and s != g for s in tagged):
            tagged.discard(g)
    # INSPIRE's "Gravitation and Cosmology" gives cosmo.general a weak prior;
    # keep it only if something else points at cosmology too
    if tagged == {"cosmo.general"} and why["cosmo.general"] == {"declared"} \
            and score["cosmo.general"] < 1.5:
        tagged.discard("cosmo.general")
    basis = set()
    for sf in tagged:
        basis |= why[sf]
    return sorted(tagged, key=lambda s: -T.SUBFIELDS[s][2]), basis


def score_event(subfields, region, etype, basis):
    if not subfields:
        return 0
    weights = sorted(((T.SUBFIELDS[s][2], T.parent(s)) for s in subfields), reverse=True)
    best_w, best_f = weights[0]
    other = [w for w, f in weights if f != best_f]
    s = best_w + (T.BONUS_SECOND_FIELD * other[0] if other else 0)
    fams = {T.parent(x) for x in subfields}
    if "cosmo" in fams and "ai" in fams:
        s += T.BONUS_COSMO_X_AI
    elif "astro" in fams and "ai" in fams:
        s += T.BONUS_ASTRO_X_AI
    if "cosmo" in fams and ("math.probability" in subfields or "ai.theory" in subfields):
        s += T.BONUS_COSMO_X_STATS
    if region == "bengaluru":
        s += T.BONUS_BENGALURU
    elif region == "india":
        s += T.BONUS_INDIA
    if etype in ("School", "Workshop"):
        s += T.BONUS_SCHOOL
    if basis == {"embedding"}:
        s *= 0.85  # judged by the embedding alone: slightly less sure
    return int(round(min(100, s)))


def classify(ev, embed_result=None, llm_result=None):
    """Returns (subfields, fields, score, basis)."""
    score, why = gather_evidence(ev, embed_result)
    subfields, basis = assign(score, why)
    if llm_result is not None:
        strong_declared = {sf for sf in subfields
                           if "declared" in why[sf] and score[sf] >= T.STRONG}
        llm_sfs = [s for s in llm_result.get("subfields", []) if s in T.SUBFIELDS]
        subfields = sorted(set(llm_sfs) | strong_declared,
                           key=lambda s: -T.SUBFIELDS[s][2])
        basis = {"llm"} | ({"declared"} if strong_declared else set())
    fields = sorted({T.parent(s) for s in subfields}, key=list(T.FIELDS).index)
    sc = score_event(subfields, ev.get("region"), ev.get("type"), basis)
    if llm_result is not None and isinstance(llm_result.get("relevance"), (int, float)):
        sc = int(round(0.5 * sc + 0.5 * max(0, min(100, llm_result["relevance"]))))
    return subfields, fields, sc, sorted(basis)
