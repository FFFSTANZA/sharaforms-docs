# SharaForms API Docs

Static documentation site for the SharaForms API, published at **https://docs.sharaforms.com** (GitHub Pages, behind Cloudflare).

## Layout

- `site/` — built static site (pure HTML + CSS, no JS). This is what GitHub Pages serves (`/site`).
- `source/api-reference/` — MDX sources for the API reference pages.
- `build.py` — static site builder.

## Rebuild

```bash
python3 build.py     # regenerates site/ from source/api-reference/
```

The builder falls back to `../docs/api-reference` (the main sharaforms repo) when `source/` is absent.

## Deploy

Push to `main`. GitHub Pages publishes from the `site/` directory (`CNAME` + `.nojekyll` live there). Cloudflare proxies `docs.sharaforms.com` → `FFFSTANZA.github.io`.
