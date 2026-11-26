"""Static site generator: data/projects.json -> site/.

Outputs:
  site/index.html                  directory index (search + category filter)
  site/project/<slug>/index.html   project profile page
  site/go/<slug>/index.html        interstitial (countdown + Continue; see
                                   docs/ADSTERRA_COMPLIANCE.md)
  site/expedited-review/index.html expedited-review page (see
                                   config/expedited_review.yml — PROPOSED tiers)
  site/static/                     copied CSS/JS
"""
import argparse
import json
import os
import shutil

try:
    import yaml
except ImportError:  # PyYAML is in requirements.txt; fall back to a tiny parser
    yaml = None

from .templates import get_environment
from ..advertising.placements import ADSTERRA_SMARTLINK_URL

DEFAULT_EXPEDITED = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "expedited_review.yml")
CASHAPP_URL = "https://cash.app/$slightlysigh"
CONTACT_EMAIL = "primecomputerpieces@gmail.com"
# General contact for the directory (shown in the site footer).
DIRECTORY_CONTACT_EMAIL = "primecomputerpieces@gmail.com"
DEFAULT_TIERS = [
    {"key": "free", "name": "Free", "donation_usd": 0,
     "wait_time": "10–14 days",
     "description": "Standard queue — no donation needed."},
    {"key": "standard", "name": "Standard", "donation_usd": 5,
     "wait_time": "3–5 days",
     "description": "Faster review than the free queue."},
    {"key": "priority", "name": "Priority", "donation_usd": 15,
     "wait_time": "24–48 hours",
     "description": "Reviewed ahead of Standard and Free submissions."},
    {"key": "same-day", "name": "Same-day", "donation_usd": 30,
     "wait_time": "Same day if submitted before 12pm ET, otherwise next day",
     "description": "Fastest review. Submit before 12pm ET for same-day review; later submissions are reviewed the next day."},
]


def load_expedited_review(config_path=DEFAULT_EXPEDITED):
    """Load expedited-review tiers; fall back to the built-in defaults."""
    if yaml is not None and os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return {
            "cashapp_url": data.get("cashapp_url", CASHAPP_URL),
            "contact_email": data.get("contact_email", CONTACT_EMAIL),
            "tiers": data.get("tiers") or DEFAULT_TIERS,
        }
    return {"cashapp_url": CASHAPP_URL, "contact_email": CONTACT_EMAIL,
            "tiers": DEFAULT_TIERS}

DEFAULT_DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "projects.json")
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "..", "..", "site")
# GitHub Pages project-site subpath:
# https://unaveragetech.github.io/open-project-directory/
# Override with --base-path "" for a root-hosted / local preview.
DEFAULT_BASE_PATH = os.environ.get("OPD_BASE_PATH", "/open-project-directory")


def load_projects(data_path):
    with open(data_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["projects"]


def generate_site(data_path=DEFAULT_DATA, out_dir=DEFAULT_OUT,
                  base_path=DEFAULT_BASE_PATH):
    projects = load_projects(data_path)
    env = get_environment()
    os.makedirs(out_dir, exist_ok=True)
    # .nojekyll: tell GitHub Pages to serve site/ as-is (no Jekyll processing).
    with open(os.path.join(out_dir, ".nojekyll"), "w", encoding="utf-8") as fh:
        fh.write("")
    counts = {"projects": 0, "profiles": 0, "interstitials": 0,
              "expedited_pages": 0}

    expedited = load_expedited_review()
    categories = sorted({c for p in projects for c in p.get("category", [])})
    tags = sorted({t for p in projects for t in p.get("tags", [])})
    for p in projects:
        p.setdefault("tags", [])
    index_html = env.get_template("directory.html").render(
        projects=projects, categories=categories, tags=tags,
        base_path=base_path, adsterra_url=ADSTERRA_SMARTLINK_URL,
        expedited_tiers=expedited["tiers"],
        cashapp_url=expedited["cashapp_url"],
        contact_email=expedited["contact_email"],
        directory_contact_email=DIRECTORY_CONTACT_EMAIL)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index_html)

    # Dedicated expedited-review page.
    expedited_dir = os.path.join(out_dir, "expedited-review")
    os.makedirs(expedited_dir, exist_ok=True)
    expedited_html = env.get_template("expedited.html").render(
        tiers=expedited["tiers"], base_path=base_path,
        cashapp_url=expedited["cashapp_url"],
        contact_email=expedited["contact_email"])
    with open(os.path.join(expedited_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(expedited_html)
    counts["expedited_pages"] = 1

    for project in projects:
        slug = project["slug"]
        profile_dir = os.path.join(out_dir, "project", slug)
        os.makedirs(profile_dir, exist_ok=True)
        html = env.get_template("project.html").render(
            project=project, base_path=base_path,
            adsterra_url=ADSTERRA_SMARTLINK_URL)
        with open(os.path.join(profile_dir, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(html)
        counts["profiles"] += 1

        go_dir = os.path.join(out_dir, "go", slug)
        os.makedirs(go_dir, exist_ok=True)
        html = env.get_template("interstitial.html").render(
            project=project, base_path=base_path,
            adsterra_url=ADSTERRA_SMARTLINK_URL,
            countdown_seconds=5)
        with open(os.path.join(go_dir, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(html)
        counts["interstitials"] += 1
        counts["projects"] += 1

    static_src = os.path.join(os.path.dirname(__file__), "..", "..", "static")
    static_dst = os.path.join(out_dir, "static")
    if os.path.isdir(static_src):
        shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
    return counts


def main():
    parser = argparse.ArgumentParser(description="Generate the static directory site.")
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--base-path", default=DEFAULT_BASE_PATH,
                        help="URL subpath the site is served under "
                             "(default /open-project-directory for GitHub Pages; "
                             "use '' for root hosting)")
    args = parser.parse_args()
    counts = generate_site(args.data, args.out, base_path=args.base_path)
    print(f"Generated site: {counts['projects']} projects, "
          f"{counts['profiles']} profile pages, "
          f"{counts['interstitials']} interstitial pages, "
          f"{counts.get('expedited_pages', 0)} expedited-review page(s) -> {args.out} "
          f"(base_path={args.base_path!r})")
    return 0


if __name__ == "__main__":
    main()
