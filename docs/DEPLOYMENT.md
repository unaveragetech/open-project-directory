# Deployment — GitHub Pages (production)

Live URL: https://unaveragetech.github.io/open-project-directory/

## How it deploys

1. Push to `main` (or run the publishing workflow manually). The
   `publishing.yml` workflow builds `site/` with the generator
   (base path `/open-project-directory`, `.nojekyll` included) and
   deploys it with `actions/upload-pages-artifact` +
   `actions/deploy-pages`. No hosting secrets are needed.
2. One-time repo setup: Settings → Pages → Build and deployment →
   Source: **GitHub Actions**. No custom domain is configured; the
   project-Pages URL above is the live address.
3. Screenshots and assets live in the repo under `static/` and are
   copied into `site/static/` by the generator.

## Local build / preview

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/python -m src.publishing.generator --data data/projects.json --out site
# Pages subpath preview: serve the repo root so /open-project-directory/ resolves,
# or rebuild with --base-path "" into a temp dir and serve that dir:
.venv/bin/python -m src.publishing.generator --base-path "" --out /tmp/opd-site
python3 -m http.server --directory /tmp/opd-site 8080
```

## Optional extras (not required for Pages)

- PostgreSQL for the catalog (`src/database/migrations/`) and the
  FastAPI service (`src/api/server.py`) for intake/search; Redis for
  queues and caching. Configure secrets in the hosting/CI environment
  only — never commit credentials. `ADSTERRA_*` is public config, not
  a secret.
- A future move to Cloudflare Pages or equivalent needs no template
  change: the generator output is plain static HTML.

## Before monetisation at scale

Obtain written Adsterra confirmation of eligibility
(see `docs/ADSTERRA_COMPLIANCE.md`).

## Reverification schedule

See `maintenance.yml` and README: HTTP/TLS daily, browser/docs weekly,
metadata/full evaluation monthly.
