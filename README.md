# SharaForms API Docs

Static documentation site for the SharaForms API, published at **https://docs.sharaforms.com**.

## Layout

- `docs/` — the entire site, hand-authored in pure HTML + CSS + vanilla JS (no framework, no build step). GitHub Pages publishes this directory. Contains `CNAME` + `.nojekyll`.
  - `styles.css` — design system: color tokens (`:root` / `[data-theme="dark"]`), typography (Inter + JetBrains Mono), topbar, sidebar, code blocks, tables, TOC, home/404 styles, responsive rules.
  - `app.js` — theme toggle (localStorage `sf-docs-theme` + `prefers-color-scheme`), sidebar search (filter + `/` shortcut), mobile nav, code copy buttons, scrollspy TOC.
  - 36 pages: `index.html`, `404.html`, `api-keys.html`, `changelog.html`, `computed-variables.html`, plus `forms/`, `submissions/`, `integrations/`, `workspaces/`, `workspace-users/`, `embedding/` subdirectories.

## Edit

Open the HTML/CSS/JS files directly and push to `main` — Pages auto-deploys from the `docs/` directory. There is intentionally no build step.

## DNS

`docs.sharaforms.com` CNAME → `fffstanza.github.io`.
