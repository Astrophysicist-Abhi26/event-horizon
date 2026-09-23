# Deploying Event Horizon v5

v4 was built but never merged, because the repository was edited through the GitHub web
upload page. v5 is deployed with `git` from the Mac terminal, then verified against the live
Action log. About 15 minutes.

## 0. One-time: let git push to GitHub

If you have never pushed from this Mac:

```bash
brew install gh          # if Homebrew is installed; otherwise https://cli.github.com
gh auth login            # GitHub.com -> HTTPS -> "Login with a web browser"
```

## 1. Get a fresh copy of the repository

```bash
mkdir -p ~/code && cd ~/code
git clone https://github.com/Astrophysicist-Abhi26/event-horizon.git
cd event-horizon
```

(Already cloned earlier? Then `cd` into it and run `git pull` instead — the bot commits
new events every day, so a stale copy will refuse to push.)

## 2. Replace the contents with v5

Unzip `event-horizon-v5.zip` in Downloads, then:

```bash
rsync -av --delete --exclude .git ~/Downloads/event-horizon-v5/ ./
git status        # review: new scraper modules, tests/, workflow, docs/index.html …
```

`--delete` removes files v5 no longer uses (the old `manual_events.yaml`, replaced by
`watchlist.yaml`).

## 3. Optional but recommended: test on your Mac first

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q tests                    # expect: 30 passed
EH_NO_EMBED=1 python scraper/scrape.py        # every source should print [ok]
```

On your Mac the sources are reachable, so this is the first true end-to-end run. If a line
shows `[error]`, note it (see "Reading the log" below) — the run continues regardless.
Then `git checkout docs/events.json` to discard the local data; the Action will regenerate it.

## 4. Commit and push

```bash
git add -A
git commit -m "Event Horizon v5: new sources, taxonomy, classifiers, frontend, tests"
git push
```

## 5. Run the workflow once by hand

GitHub → your repo → **Actions** → **Update events** → **Run workflow** → tick
*Also send the weekly digest now* → **Run workflow**.

The first run takes ~3–6 minutes (it downloads the ~130 MB embedding model once; later
runs use the cache).

## 6. Verify — reading the log

Open the run → job **scrape** → step **Scrape, classify and score**:

```
[ok   ] DESC Cosmology Meetings: 57 raw (1.2s)
[ok   ] CADC Astronomy Meetings: 123 raw (0.8s)
[ok   ] INSPIRE conferences: 1000 raw (9.4s)
[low  ] IMSc Chennai: 2 raw …
[error] IUCAA (events outside IUCAA): HTTPError: 404 …
...
Wrote 1432 events (918 classified) -> docs/events.json
Classifiers: {"embedding": {"status": "on", "detail": "LOO accuracy 84%; margin ≥ 0.031 gives 92% precision on 61% of labels"}, ...}
```

- `ok` — working. `low` — fewer events than expected; fine for small pages.
- `error` / `empty` — that source contributed nothing. The others are unaffected.
  For an institute page, open its URL in a browser: if the page moved, update the URL in
  `scraper/institutes.yaml`; if it genuinely lists nothing, delete the entry.
- **Embedding classifier** — `on` means it calibrated itself above 90 % precision.
  `off` with a reason means it refused to guess; everything else still works.

Then open the site (Pages redeploys ~1 minute after the Action commits) and check
**Source health** at the bottom — it mirrors the log.

## 7. Notifications

You should receive a **Weekly digest** Issue (you ticked the box) and probably an
**urgent** Issue listing the most relevant newly found events (capped at 25 on the first
run). GitHub emails you for Issues on your own repo by default; if not, check
github.com → Settings → Notifications → Email.

## 8. Optional — Option C (Claude classification)

Settings → Secrets and variables → Actions → **New repository secret** →
name `ANTHROPIC_API_KEY`, value = your key from console.anthropic.com. Next run, the health
panel shows the Claude classifier as `on`.

## Everyday use afterwards

- New ad-hoc conference: add it to `scraper/watchlist.yaml`, then
  `git pull && git add -A && git commit -m "watchlist" && git push`.
- Always `git pull` before editing — the bot commits every morning.
