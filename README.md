# SharaForms API Docs

Static documentation site for the SharaForms API, published at **https://docs.sharaforms.com** (GitHub Pages → Cloudflare → domain).

## Layout

- `docs/` — built static site (pure HTML + CSS, no JS). GitHub Pages publishes this directory (`/docs`). Contains `CNAME` + `.nojekyll`.
- `source/` — MDX sources: `api-reference/`, `features/computed-variables.mdx`, `embedding/javascript-sdk.mdx`.
- `build.py` — static site builder (writes to `docs/` here, or `site/` in the main repo layout).

## Rebuild

```bash
python3 build.py     # regenerates docs/ from source/
```

Push to `main` to publish (Pages auto-deploys from the `docs/` directory).

## DNS

`docs.sharaforms.com` → `CNAME` → `fffstanza.github.io` (proxied, Cloudflare zone `sharaforms.com`). Domain registered at Hostinger; nameservers point at Cloudflare.
