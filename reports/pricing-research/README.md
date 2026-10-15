# Dynamic pricing research dashboard

Open `index.html` in a browser. It is self-contained: no server, installation, API key, external fonts or CDN required. JavaScript must be enabled. Repository-relative evidence links work when the surrounding repository is available.

Features: executive verdict, three-approach comparison, 14/28/90-day selector, scenario results, historical comparisons, protocol timeline, expandable methodology, and print styling. Use **Print / Save PDF** for a shareable report. RCA/explanation-layer work is excluded.

Rebuild from the repository root:

```sh
python3 reports/pricing-research/build.py
```

Edit `template.html`, then rebuild; do not hand-edit generated `index.html`. `source_manifest.json` records source checksums. The dashboard embeds only aggregate results. No new model runs or API calls are needed.

`LINKEDIN_DRAFT.md` is a draft for review, not a published post. GitHub's file viewer shows HTML source; to view the dashboard, download/open it locally or separately configure static hosting. This change does not enable GitHub Pages or publish to LinkedIn.

Verification: rendered in the in-app browser; the 14-day selector updated both the pilot chart and scenario table correctly. Initial 90-day values matched saved aggregates. Responsive single-column layout inspected in the narrow preview.
