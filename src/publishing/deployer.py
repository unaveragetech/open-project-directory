"""Deployment helpers.

Production target is GitHub Pages (Jesse's direction, 2026-11-25):
https://unaveragetech.github.io/open-project-directory/
The generator output is plain static HTML, so a future move to another
static host (e.g. Cloudflare Pages) would need no template changes.
Deployment itself is performed by the publishing workflow
(`.github/workflows/publishing.yml`) via actions/deploy-pages; this
module validates the built output before that step runs.
"""
import os

PAGES_URL = "https://unaveragetech.github.io/open-project-directory/"
BASE_PATH = "/open-project-directory"


def validate_site_output(site_dir):
    """Check a generated site/ dir is complete. Returns (ok, [errors])."""
    errors = []
    index = os.path.join(site_dir, "index.html")
    if not os.path.isfile(index):
        errors.append("missing site/index.html")
    if not os.path.isfile(os.path.join(site_dir, ".nojekyll")):
        errors.append("missing site/.nojekyll")
    project_dir = os.path.join(site_dir, "project")
    if not os.path.isdir(project_dir) or not os.listdir(project_dir):
        errors.append("no project pages generated")
    go_dir = os.path.join(site_dir, "go")
    if not os.path.isdir(go_dir) or not os.listdir(go_dir):
        errors.append("no interstitial pages generated")
    return (not errors), errors


def deploy_command(site_dir, project_name="open-project-directory"):
    """Return a description of the deploy step (CI does the actual deploy).

    GitHub Pages deploy is done by .github/workflows/publishing.yml
    (upload-pages-artifact + deploy-pages); there is no Wrangler/CLI
    command to run by hand.
    """
    return ["github-pages", "actions/deploy-pages", site_dir, project_name]
