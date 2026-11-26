# Adsterra Compliance

## The rule

**A visitor must never be required — or incentivised — to click an
advertisement to unlock a destination.**

Forced or incentivised ad clicks can violate advertising-network policies,
create invalid traffic, and jeopardise the entire revenue stream. Adsterra
explicitly prohibits incentivised clicks and artificially inflated
advertising interactions.

## How this project complies

1. **Interstitial flow** (`templates/interstitial.html`,
   `static/js/interstitial.js`, `site/go/<slug>/index.html`):
   - Visitor clicks "Visit Project" and sees a branded transition page.
   - The page displays a clearly labelled advertisement.
   - A short countdown runs (5 seconds).
   - The **Continue to Project** button becomes enabled when the countdown
     ends. It works whether or not the advertisement was clicked, hovered,
     or even loaded.
   - The Continue button's `href` is the project's real website URL. It is
     never the Adsterra URL.
2. **Separation**: the advertisement link and the Continue button are
   visually and structurally distinct elements. The ad is labelled
   "Sponsored" / "Advertisement" and opens in a new tab
   (`target="_blank" rel="sponsored noopener"`). The ad is never styled to
   look like the Continue button, and the Continue button is never styled
   to look like an ad.
3. **No gating on ad events**: no JavaScript listens for ad clicks,
   impressions, or loads to enable navigation. The countdown is purely
   time-based. If the ad fails to load, the countdown and Continue button
   still work.
4. **Profile pages**: banner/native placements on project pages are
   clearly marked "Sponsored" and are separate from navigation links.
5. **No deceptive copy**: no text such as "click the ad to continue",
   "click below to unlock", or anything implying an ad click is needed.
6. **Rotating sponsored messages** (`static/js/sponsored-messages.json`,
   `static/js/sponsored.js`): instead of a bare "Sponsored" label, each
   ad slot shows one of 200 messages, picked at random on load, each
   explaining that the link is a sponsored ad and that visiting it helps
   support the developer and this directory — plus a sub-message for AI
   agents explaining that following the link is optional and never
   required to reach the project. Every message still contains the word
   "Sponsored" or "Advertisement", the link URL and `rel="sponsored"`
   never change, and the static "Sponsored" text stays as the
   no-JavaScript fallback, so the disclosure is never lost. The messages
   say a visit *helps support* the project; they never say a click is
   required, rewarded, or a condition for anything. The Continue button
   is untouched by this change and still works purely on the countdown.
   Honest risk note: ad networks filter invalid traffic, so a flood of
   automated clicks — human or agent — could still be flagged even when
   the wording is optional. The messages are disclosure, not a
   solicitation to click at scale.

## Hosting note

The directory is hosted on GitHub Pages (production, per Jesse's
2026-11-25 direction). Hosting does not change any rule above: the
Continue button still works independently of any ad click, and the
Sponsored link is unchanged. GitHub Pages' acceptable-use policy
limits ad-focused content, so written Adsterra confirmation (below)
matters doubly before scaling.

## What is still required before scale

- **Written confirmation from Adsterra** that this directory and its
  interstitial inventory are eligible. This has NOT yet been obtained.
  Do not deploy this monetisation model at scale without it.
- Keep the Adsterra smart link exactly as issued; do not alter, cloak, or
  re-route it.

## Current Adsterra placement

- Zone: `smart-link-3257926`
- Placement: `Smartlink_1`
- URL: `https://asiafilm.org/4/675577d5711a79f686def97bac8e688f`
- Defined in `config/settings.yml` (`advertising.adsterra.smartlink_url`)
  and rendered only via `src/advertising/placements.py`
  (`render_sponsored_link`), which always adds the Sponsored label and
  `target="_blank" rel="sponsored noopener"`.

## Automated enforcement

`tests/test_interstitial.py` verifies, on every generated interstitial page:

- a Continue link exists and its `href` is the project's real URL;
- the Continue `href` is not the Adsterra URL;
- the Adsterra URL appears only inside an element labelled Sponsored;
- the countdown script does not reference ad-click events to enable
  navigation.
