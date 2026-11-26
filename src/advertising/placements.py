"""Adsterra placements.

Single source of truth for the Adsterra smart link. The link is rendered
ONLY as a clearly labelled Sponsored link opening in a new tab, and NEVER
as (or disguised as) a navigation/Continue button. See
docs/ADSTERRA_COMPLIANCE.md.
"""
import html

ADSTERRA_SMARTLINK_URL = "https://asiafilm.org/4/f3a2a61554ddd109d393d78e61fa4202"
ADSTERRA_ZONE = "smart-link-3257926"
ADSTERRA_PLACEMENT = "Smartlink_1"


def render_sponsored_link(url=ADSTERRA_SMARTLINK_URL, label="Sponsored"):
    """Return a Sponsored ad link. Always labelled, always new tab."""
    safe_url = html.escape(url, quote=True)
    safe_label = html.escape(label)
    return (
        f'<a class="sponsored-link" href="{safe_url}" target="_blank" '
        f'rel="sponsored noopener" data-ad-network="adsterra" '
        f'data-ad-zone="{ADSTERRA_ZONE}">{safe_label}</a>'
    )


def render_banner_slot(placement="banner-top"):
    """A labelled banner ad slot for a project profile page."""
    return (
        f'<div class="ad-slot" data-placement="{html.escape(placement)}" '
        f'data-ad-network="adsterra">'
        f'<span class="ad-label">Advertisement</span>'
        f"{render_sponsored_link()}"
        f"</div>"
    )
