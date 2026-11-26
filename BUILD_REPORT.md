# Open Project Directory — Build Report

**Date:** 2026-11-25
**Location:** `~/workspace/open-project-directory/`
**Status:** Built locally. Not pushed to GitHub, not deployed live.

## What was built

A complete working repository implementing the outline (§1–§14):

- **Submission intake** — GitHub issue form templates
  (`.github/ISSUE_TEMPLATE/submit-project.yml`, `report-project.yml`) with
  required-field validation; parser / validator / normalizer in
  `src/submission/` (issue-body parsing, URL normalisation, slugify,
  duplicate detection by website/slug).
- **Automated inspection (real code, not stubs)** —
  `src/inspection/http_inspector.py` (httpx: DNS, TLS via `ssl`,
  redirect chains with per-redirect revalidation, security headers,
  robots.txt/sitemap.xml, size limits), `browser_inspector.py`
  (Playwright headless Chromium: rendering, console/JS errors, broken
  images, empty/placeholder detection, mobile viewport, screenshot),
  `documentation.py` (BeautifulSoup extraction, every item tied to a
  source URL), `scoring.py` (weights Website 20 / Security-HTTPS 15 /
  Content 20 / Documentation 15 / Functionality 15 / Metadata 10 /
  Trust 5 = 100; bands 85+ auto-approve, 70–84 manual review, 50–69
  request corrections, <50 reject; malware/phishing/deceptive-redirect/
  dangerous-download hard-fails override the score).
- **Security** — `src/inspection/security_inspector.py`: SSRF guards
  blocking localhost, private ranges, link-local and cloud-metadata
  `169.254.169.254`, non-http(s) schemes; DNS revalidated after redirects.
- **Intelligence** — `src/intelligence/` extractor (extractive only),
  metadata normaliser, summariser with an explicit no-invention rule
  (LLM may only rephrase supplied source text).
- **Page generation** — Jinja2 templates (`templates/project.html`,
  `directory.html`, `interstitial.html`) + `src/publishing/generator.py`.
  Generates `site/index.html` (search + category/free/OSS filters),
  `site/project/<slug>/index.html` profiles, and
  `site/go/<slug>/index.html` interstitials; copies `static/` assets.
**Database (optional)** — SQLAlchemy models + repository + migration
  `001_initial_schema.py` for projects, inspections, pages, traffic,
  advertising, submissions (PostgreSQL; GitHub issue ID stored only as a
  link, never as the database). Not required for a GitHub Pages deploy.
- **API** — FastAPI skeleton (`src/api/server.py`, `routes.py`).
- **Advertising** — `src/advertising/placements.py` (single source of
  truth for the Adsterra link) and `analytics.py` (records only actual
  impressions/clicks; no forecast revenue).
**Workflows** — `submission.yml`, `inspection.yml`, `publishing.yml`
  (builds `site/` and deploys to GitHub Pages via
  `upload-pages-artifact` + `deploy-pages`, on push to `main` and on
  manual dispatch), `maintenance.yml` (daily HTTP/TLS, weekly
  browser/docs reverification).
- **Config** — `config/settings.yml`, `categories.yml`,
  `quality_rules.yml` (weights + bands + hard fails).
- **Docs** — `README.md`, `docs/ARCHITECTURE.md`,
  `docs/DEPLOYMENT.md`, `docs/ADSTERRA_COMPLIANCE.md`.

## Adsterra compliance (verified)

- Smart link used, exactly as issued: `https://asiafilm.org/4/f3a2a61554ddd109d393d78e61fa4202`
  (zone `smart-link-3257926`, placement `Smartlink_1`, from
  `~/workspace/user/files/Pub_Codes_3257926_1795549772_0_pwrt.txt`).
- It appears **only** as a clearly labelled "Sponsored" link opening in a
  new tab (`target="_blank" rel="sponsored noopener"`), once per page.
- Interstitial: 5-second countdown, then the **Continue to Project**
  button enables. The countdown is purely time-based; the button's `href`
  is the project's real URL, never the Adsterra URL. No ad-click,
  impression, or load event gates navigation. The ad is never disguised
  as the Continue button. Enforced by `tests/test_interstitial.py`.
- Economics table in the README is labelled **illustrative only** — no
  invented Adsterra CPMs or earnings forecasts.

## Hosting decision — revised 2026-11-25 at Jesse's direction

**Production hosting is now mass GitHub Pages**, at
https://unaveragetech.github.io/open-project-directory/ — easier, very
light per project, deploys as soon as the site is ready. GitHub = Issues
intake + Actions + source + Pages hosting. PostgreSQL is optional
(catalog only). Screenshots/assets live in the repo under `static/`.

One factual note, kept in README / ARCHITECTURE.md / ADSTERRA_COMPLIANCE.md:
GitHub Pages is intended primarily for personal/organisational projects
and its acceptable-use policy limits ad-focused content, so mass
ad-monetised Pages hosting carries a policy risk. That is Jesse's explicit
choice; a future move to Cloudflare Pages remains possible without
changing page templates, because the generator output is plain static
HTML.

## Seed data (`data/projects.json`, 4 projects)

Real projects only, no invented features; each with source URLs and
`last_verified: 2026-11-25`:

- **TokenBroker** — tokenbroker.org; prepaid OpenAI-compatible gateway,
  $15/mo flat or pay-as-you-go, Claude Code via /v1/messages, PC + phone
  workers. Score 90.
- **Collectify** — unaveragetech.github.io/collectify-app; free offline
  no-account TCG app, 54 games, 440k+ cards. Score 88.
- **Dead Grid** — unaveragetech.github.io/dead-grid; open-beta zombie
  survival on the player's real US neighbourhood map. Score 87.
- **Example AI Assistant** — clearly marked as an example listing
  (example.com). Score 93.

## Test results

```
.venv/bin/pytest -q
23 passed in 0.13s
```

Coverage: parser, validator/normalizer/duplicate detection, scoring
bands + perfect-score + hard-fail override + weights sum to 100, SSRF
blocking (localhost, private ranges, 169.254.169.254 metadata,
non-http schemes, redirect revalidation), interstitial compliance
(Continue href = real project URL, never the ad URL; ad only as
Sponsored; countdown timer-based), generated-site integrity.

One fix during the build: `select_jinja_autoescape` does not exist in
the installed Jinja2 — corrected to `select_autoescape`. One test
assertion was also tightened (it tripped on the word "advertisement" in
a JS comment; it now checks for actual click-gating behaviour).

## Generator output

```
.venv/bin/python -m src.publishing.generator --data data/projects.json --out site
Generated site: 4 projects, 4 profile pages, 4 interstitial pages -> site
```

Verified in the generated site: `site/index.html`, 4 profile pages
(`site/project/<slug>/index.html`), 4 interstitial pages
(`site/go/<slug>/index.html`), `site/static/css/main.css`,
`site/static/js/directory.js`, `site/static/js/interstitial.js`.
Each interstitial's Continue button points at the real project URL
(tokenbroker.org, collectify-app, dead-grid, example.com); the Adsterra
URL appears exactly once per page, inside a Sponsored-labelled link.
`python -m compileall` passes for all of `src/`, `scripts/`, `tests/`.

## Caveats

- **Live re-verification of the seed URLs from this VM was not possible:**
  outbound HTTPS from this sandbox goes through an egress proxy and
  direct connections fail; the seed entries therefore carry
  `last_verified: 2026-11-25` from prior live verification, not from a
  fresh check in this build. Re-run the inspection workflow (or
  `src/inspection/http_inspector.py --reverify-all`) from an environment
  with normal internet access before publishing.
- Playwright browser inspection is implemented but its browser binary was
  not installed/exercised in this build (no `playwright install` run);
  the browser inspector imports Playwright lazily so unit tests and the
  HTTP path do not need it.

## NOT done

- **No GitHub repository created, no code pushed** (`gh` is not logged
  in; parent to handle). Intended repo: `unaveragetech/open-project-directory`
  (Jesse's GitHub account is `unaveragetech`); templates already point there.
- **No live deployment yet** (no GitHub repo created/pushed, so no
  Pages site exists yet; no PostgreSQL instance provisioned — optional).
- **No written Adsterra confirmation** that this directory/interstitial
  inventory is eligible — still required before deploying monetisation
  at scale (see `docs/ADSTERRA_COMPLIANCE.md`).
- No submissions received yet; the pipeline has been exercised only
  against the seed data and the test suite.
- No secrets are stored in the repo. `.venv/` and `site/` are gitignored;
  dependencies are pinned in `requirements.txt`.

## Revision 2026-11-25 22:01–22:02 EST — GitHub Pages + tag search

### GitHub Pages hosting
- `publishing.yml` rewritten: push to `main` (or manual dispatch) →
  build `site/` with the generator → validate → `configure-pages` →
  `upload-pages-artifact` (path `site`) → `deploy-pages` (environment
  `github-pages`, `pages: write` + `id-token: write` permissions).
- `config/settings.yml`: `base_url`
  `https://unaveragetech.github.io/open-project-directory/`,
  `base_path: "/open-project-directory"`, `hosting: "github-pages"`,
  `storage: "repo-static"`, `database: "postgresql-optional"`.
- Generator: `--base-path` (default `/open-project-directory`,
  `OPD_BASE_PATH` env override, `""` for root/local preview), passes
  `base_path` to all templates, writes `site/.nojekyll`.
- Templates + `src/publishing/deployer.py` updated: all internal links
  and static assets use `{{ base_path }}/…`; no root-absolute
  `/static/`, `/project/`, `/go/` or `/` links remain. Deployer
  validates `.nojekyll` exists and no longer references Wrangler.
- README / ARCHITECTURE.md / DEPLOYMENT.md / ADSTERRA_COMPLIANCE.md
  rewritten to GitHub Pages as production, with the one-paragraph
  factual Pages-ToS note and the Cloudflare fallback option.

### Tag search (new requirement, same revision)
- Tags added to `data/projects.json` (real tags only): TokenBroker
  `ai, api-gateway, developer-tools, llm, claude-code`; Collectify
  `tcg, trading-cards, games, offline, utilities`; Dead Grid
  `games, zombie-survival, openstreetmap, android, browser-game`;
  Example `ai, developer-tools, code-analysis`.
- `src/submission/normalizer.py` slugifies/dedupes tags;
  `validator.py` checks tags are a string or list of strings.
- Index (`templates/directory.html` + `static/js/directory.js`):
  search box filters live by name, description, category AND tags;
  tag chips for all 15 tags (click toggles, click again clears,
  multiple tags combine with AND); category filter, free/OSS toggles;
  result count ("Showing X of Y projects"); empty state
  ("No projects match — try a different search, tag or filter");
  honours `?tag=`, `?tags=a,b`, `?q=` and `?category=` on load.
- Every project has its own separate profile page
  (`site/project/<slug>/index.html`) with name, description, tags as
  clickable links to `index.html?tag=<tag>`, destination, docs, repo,
  pricing, verification status, last verified, quality score,
  Sponsored Adsterra link once, and a Visit button via
  `/go/<slug>/` interstitial.

### Revision test results
```
.venv/bin/pytest -q
29 passed in 0.25s   (was 23; +6 in tests/test_tags_search.py)
```
```
.venv/bin/python -m src.publishing.generator --data data/projects.json --out site
Generated site: 4 projects, 4 profile pages, 4 interstitial pages -> site (base_path='/open-project-directory')
```
- Node DOM-stub harness (`/tmp/opd-dom-test.js`, jsdom not installed so
  a minimal stub drove the real `directory.js` against the generated
  `site/index.html`): 14/14 checks passed — default 4 shown; `?tag=ai`
  → 2; `?tags=ai,developer-tools` → 2; `?tags=ai,claude-code` → 1;
  search "zombie" → 1; search "tcg" → 1; games chip click → 2, click
  again → 4; no-match → 0 with empty state visible and "0 of 4";
  Clear all → 4.
- Pages-subpath serving check: copied `site/` to
  `/tmp/opd-preview/open-project-directory`, served locally — HTTP 200
  for `/open-project-directory/`, `/project/tokenbroker/`,
  `/go/tokenbroker/`, `/project/collectify/`, `/static/css/main.css`,
  `/static/js/directory.js`.
- Adsterra unchanged: URL appears exactly once per page as a Sponsored
  link; interstitial Continue still points at the real project URL
  (e.g. `https://tokenbroker.org`), never the ad URL.
- `publishing.yml` parses as valid YAML.

## Revision 2026-11-25 22:06 EST — Expedited review (proposed tiers)

**⚠️ Proposed, not confirmed:** donation amounts and wait times are
suggestions for Jesse to confirm before going live. Labelled
PROPOSED/DRAFT in `config/expedited_review.yml`,
`docs/EXPEDITED_REVIEW.md`, the expedited page, and the README.

- **Tiers:** Free $0 — 10–14 days · Standard $5 — 3–5 days ·
  Priority $15 — 24–48 hours · Same-day $30 — same day if submitted
  before 12pm ET, otherwise next day.
- **Flow:** donate via Cash App https://cash.app/$slightlysigh, then
  email primecomputerpieces@gmail.com with the transaction code +
  project name + GitHub issue number. The code is verified against
  the donation and the issue before the submission joins that queue.
- **Policy stated everywhere:** a donation moves a submission up the
  review queue only — it does **not guarantee approval**; quality and
  safety checks still apply, and a failed submission is not refunded
  automatically (draft policy).
- **Files:** `config/expedited_review.yml` (tiers, Cash App URL,
  contact email), `docs/EXPEDITED_REVIEW.md` (full instructions),
  `templates/expedited.html` → `site/expedited-review/index.html`,
  Expedited Review section + nav link on the directory index,
  `.github/ISSUE_TEMPLATE/submit-project.yml` (expedited_review
  dropdown + transaction_code + contact_email, with the no-guarantee
  note), `src/publishing/generator.py` (`load_expedited_review()`,
  generates the expedited page), `src/submission/parser.py`
  (`parse_expedited_tier()`, expedited field headings),
  `src/submission/validator.py` (paid tiers require a transaction
  code; Free needs none; contact email format checked), README
  Expedited Review section.
- **Hosting, tags, Adsterra unchanged** by this revision.

### Revision test results
```
.venv/bin/pytest -q
37 passed in 0.36s   (was 29; +8 in tests/test_expedited.py)
```
```
.venv/bin/python -m src.publishing.generator --data data/projects.json --out site
Generated site: 4 projects, 4 profile pages, 4 interstitial pages, 1 expedited-review page(s) -> site (base_path='/open-project-directory')
```
Verified: `site/expedited-review/index.html` exists and contains the
Cash App URL and `primecomputerpieces@gmail.com`, all four tiers with
their wait times, the 12pm ET Same-day cutoff, and the
no-guarantee wording; the index links to `/expedited-review/` and
lists the tiers. Issue-template and expedited config parse as valid YAML.
