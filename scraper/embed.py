"""
Option B — local embedding classifier (free, no API key).

A small sentence-embedding model (BAAI/bge-small-en-v1.5 via `fastembed`,
~130 MB, CPU-only) turns each event's title + description into a vector.
Each sub-field gets a centroid built from its prototype description
(taxonomy.PROTOTYPES) plus every hand-labelled example in labels.yaml.
Off-topic "negative" classes compete too, so an event about genomics is not
forced into a physics field.

Self-calibration
----------------
We never hard-code a similarity threshold. Each run we do leave-one-out on
labels.yaml: classify every labelled title with its own vector removed from
its centroid, record (margin, correct?) where margin = best sim - 2nd best
sim, and choose the smallest margin at which precision >= TARGET_PRECISION.
If no margin reaches that precision the classifier disables itself and says
so in the health report. Add labelled titles to improve it.

If fastembed or the model is unavailable the pipeline simply runs without
Option B (keywords + declared codes still work).
"""

import os

import numpy as np
import yaml

import taxonomy as T

MODEL = "BAAI/bge-small-en-v1.5"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         ".cache", "fastembed")
TARGET_PRECISION = 0.90
MIN_COVERAGE = 0.25          # calibration must accept at least this share
SUPPORT_STRENGTH = 0.4       # evidence added when confident-ish but below margin
CONFIDENT_STRENGTH = 1.0     # evidence added when above calibrated margin
LABELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "labels.yaml")


class FastEmbedEncoder:
    def __init__(self):
        from fastembed import TextEmbedding  # imported lazily
        self.m = TextEmbedding(model_name=MODEL, cache_dir=CACHE_DIR)

    def __call__(self, texts):
        v = np.array(list(self.m.embed(list(texts))), dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True).clip(1e-9)


def _event_text(ev):
    return (ev.get("title") or "") + ". " + (ev.get("description") or "")[:600]


class EmbeddingClassifier:
    def __init__(self, encoder=None, labels_path=LABELS):
        self.status = "off"
        self.detail = ""
        self.margin = None
        try:
            self.enc = encoder or FastEmbedEncoder()
        except Exception as exc:  # fastembed missing / model download failed
            self.enc = None
            self.detail = f"encoder unavailable: {exc.__class__.__name__}: {exc}"[:200]
            return
        classes = {**T.PROTOTYPES, **T.NEGATIVE_PROTOTYPES}
        self.classes = list(classes)
        with open(labels_path) as f:
            self.labels = [(t, l) for t, l in (yaml.safe_load(f) or []) if l in classes]
        proto_v = self.enc([classes[c] for c in self.classes])
        lab_v = self.enc([t for t, _ in self.labels]) if self.labels else np.zeros((0, proto_v.shape[1]))
        self.lab_v = lab_v
        idx = {c: i for i, c in enumerate(self.classes)}
        self.lab_idx = np.array([idx[l] for _, l in self.labels], dtype=int)
        # centroid sums (prototype counts double: it is the definition)
        self.sums = 2.0 * proto_v.copy()
        self.counts = np.full(len(self.classes), 2.0)
        for v, i in zip(lab_v, self.lab_idx):
            self.sums[i] += v
            self.counts[i] += 1
        self._calibrate()

    def _centroids(self, sums):
        c = sums / self.counts[:, None]
        return c / np.linalg.norm(c, axis=1, keepdims=True).clip(1e-9)

    def _predict(self, vecs, centroids):
        sims = vecs @ centroids.T
        order = np.argsort(-sims, axis=1)
        top, second = order[:, 0], order[:, 1]
        rows = np.arange(len(vecs))
        return top, sims[rows, top] - sims[rows, second]

    def _calibrate(self):
        if len(self.labels) < 20:
            self.status, self.detail = "off", "fewer than 20 labelled examples"
            return
        preds, margins = [], []
        for k, (v, i) in enumerate(zip(self.lab_v, self.lab_idx)):
            sums = self.sums.copy()
            sums[i] -= v
            counts_i = self.counts[i]
            self.counts[i] -= 1
            top, mg = self._predict(v[None, :], self._centroids(sums))
            self.counts[i] = counts_i
            preds.append(top[0])
            margins.append(mg[0])
        preds, margins = np.array(preds), np.array(margins)
        correct = preds == self.lab_idx
        # scan thresholds from permissive to strict
        best = None
        for thr in sorted(set(np.round(margins, 4))):
            keep = margins >= thr
            if keep.sum() == 0:
                break
            prec = correct[keep].mean()
            cov = keep.mean()
            if prec >= TARGET_PRECISION and cov >= MIN_COVERAGE:
                best = (thr, prec, cov)
                break
        self.loo_accuracy = float(correct.mean())
        if best is None:
            self.status = "off"
            self.detail = (f"calibration failed: LOO accuracy {correct.mean():.0%}, "
                           f"no margin reaches {TARGET_PRECISION:.0%} precision")
            return
        self.margin = float(best[0])
        self.centroids = self._centroids(self.sums)
        self.status = "on"
        self.detail = (f"LOO accuracy {correct.mean():.0%}; margin ≥ {best[0]:.3f} gives "
                       f"{best[1]:.0%} precision on {best[2]:.0%} of labels")

    def classify_many(self, events):
        """-> list of (subfield, strength) or None, aligned with events."""
        if self.status != "on" or not events:
            return [None] * len(events)
        out = []
        B = 256
        for s in range(0, len(events), B):
            vecs = self.enc([_event_text(e) for e in events[s:s + B]])
            top, mg = self._predict(vecs, self.centroids)
            for t, m in zip(top, mg):
                cls = self.classes[t]
                if cls.startswith("neg."):
                    out.append(("neg", float(m)))
                elif m >= self.margin:
                    out.append((cls, CONFIDENT_STRENGTH))
                else:
                    out.append((cls, SUPPORT_STRENGTH))
        return out
