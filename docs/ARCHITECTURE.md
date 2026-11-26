# Architecture

Five subsystems: (1) submission/intake, (2) automated website intelligence
and QA, (3) static page generation and publishing, (4) centralised catalog
and discovery, (5) monetisation and traffic analytics.

```
GitHub Issue  ->  Actions worker (inspect -> score -> decide)
             ->  Page Builder (Jinja2)  ->  GitHub Pages (production)
             ->  PostgreSQL catalog (optional) ->  Directory index + search
             ->  Adsterra placements (compliant; see ADSTERRA_COMPLIANCE.md)
```

## Hosting decision (locked, revised 2026-11-25 at Jesse's direction)

- GitHub Issues: submission. GitHub Actions: automated processing.
  GitHub repository: templates and source code.
- **Production hosting: GitHub Pages** at
  https://unaveragetech.github.io/open-project-directory/ — easy, very
  light per project, deploys as soon as the site is ready. Screenshots /
  assets live in the repo under `static/`. One factual note: GitHub Pages
  is intended primarily for personal/organisational projects and its
  acceptable-use policy limits ad-focused content, so this carries a
  policy risk; it is Jesse's explicit choice, and a future move to
  Cloudflare Pages remains possible without changing page templates
  (generator output is plain static HTML).
- **Database: PostgreSQL (optional).** GitHub is not the database.

## Approval decision (locked)

Automated approval with manual-review exceptions (score bands in README
and `config/quality_rules.yml`).

## Advertising decision (locked)

Adsterra placements + compliant interstitials, never forced clicks
(see `docs/ADSTERRA_COMPLIANCE.md`).

## Pipeline stages

Issue Listener → Submission Normalizer → Network Inspector →
Browser Inspector → Documentation Analyzer → Quality Evaluator →
Approval Controller → Page Builder → Publisher → GitHub Reporter.

## Security model

Public GitHub issues are untrusted input. See README "Security" and
`src/inspection/security_inspector.py`: minimum token permissions, no
execution of submitted code, SSRF guards (localhost/private/link-local/
metadata blocked, DNS revalidated after redirects), size/time/depth
limits, HTML sanitisation.
