#!/usr/bin/env python3
"""Build the SharaForms API docs static site from docs/api-reference/*.mdx.

Output: docs-website/site/ (pure HTML + CSS, no JS, no external deps).
"""

import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_SOURCE = ROOT / "source" / "api-reference"
MDX_DIR = _SOURCE if _SOURCE.is_dir() else ROOT.parent / "docs" / "api-reference"
OUT = ROOT / "docs" if _SOURCE.is_dir() else ROOT / "site"

SITE_NAME = "SharaForms Docs"
SITE_URL = "https://docs.sharaforms.com"
BASE_URL = "https://api.sharaforms.com"

NAV = [
    (
        "Overview",
        [
            ("Introduction", "index.html"),
            ("API Keys", "api-keys.html"),
            ("Changelog", "changelog.html"),
        ],
    ),
    (
        "Forms",
        [
            ("List Workspace Forms", "forms/list-workspace-forms.html"),
            ("Create Form", "forms/create-form.html"),
            ("Get Form", "forms/get-form.html"),
            ("Update Form", "forms/update-form.html"),
            ("Delete Form", "forms/delete-form.html"),
        ],
    ),
    (
        "Submissions",
        [
            ("Create Submission (Public)", "submissions/create-submission.html"),
            ("List Submissions", "submissions/list-submissions.html"),
            ("Export Submissions (CSV)", "submissions/export-submissions-csv.html"),
            ("Check Export Status", "submissions/export-status.html"),
            ("Update Submission", "submissions/update-submission.html"),
            ("Delete Submission", "submissions/delete-submission.html"),
        ],
    ),
    (
        "Integrations & Webhooks",
        [
            (
                "Create Webhook Integration",
                "integrations/create-webhook-integration.html",
            ),
            (
                "Update Webhook Integration",
                "integrations/update-webhook-integration.html",
            ),
            (
                "Delete Webhook Integration",
                "integrations/delete-webhook-integration.html",
            ),
            ("List Form Integrations", "integrations/list-form-integrations.html"),
            ("List Webhook Events", "integrations/list-webhook-events.html"),
            ("Validating Webhook Signatures", "integrations/webhook-security.html"),
        ],
    ),
    (
        "Workspaces",
        [
            ("List Workspaces", "workspaces/list-workspaces.html"),
            ("Create Workspace", "workspaces/create-workspace.html"),
            ("Update Workspace", "workspaces/update-workspace.html"),
            ("Delete Workspace", "workspaces/delete-workspace.html"),
        ],
    ),
    (
        "Workspace Users",
        [
            ("List Workspace Users", "workspace-users/list-workspace-users.html"),
            ("List Workspace Invites", "workspace-users/list-workspace-invites.html"),
            ("Add Workspace User", "workspace-users/add-workspace-user.html"),
            (
                "Update Workspace User Role",
                "workspace-users/update-workspace-user-role.html",
            ),
            ("Remove Workspace User", "workspace-users/remove-workspace-user.html"),
            ("Resend Workspace Invite", "workspace-users/resend-workspace-invite.html"),
            ("Cancel Workspace Invite", "workspace-users/cancel-workspace-invite.html"),
            ("Leave Workspace", "workspace-users/leave-workspace.html"),
        ],
    ),
    (
        "Guides",
        [
            ("Computed Variables", "computed-variables.html"),
            ("JavaScript SDK (Embedding)", "embedding/javascript-sdk.html"),
            ("Embed Editor", "embedding/editor-embed.html"),
        ],
    ),
]

EXTRA_SOURCES = [
    (
        "computed-variables",
        (ROOT / "source" / "features" / "computed-variables.mdx")
        if _SOURCE.is_dir()
        else ROOT.parent / "docs" / "features" / "computed-variables.mdx",
    ),
    (
        "embedding/javascript-sdk",
        (ROOT / "source" / "embedding" / "javascript-sdk.mdx")
        if _SOURCE.is_dir()
        else ROOT.parent / "docs" / "embedding" / "javascript-sdk.mdx",
    ),
    (
        "embedding/editor-embed",
        (ROOT / "source" / "embedding" / "editor-embed.mdx")
        if _SOURCE.is_dir()
        else ROOT.parent / "docs" / "embedding" / "editor-embed.mdx",
    ),
]


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def inline(text: str) -> str:
    """Convert inline markdown (bold, code, links, italic) to HTML."""
    text = esc(text)
    # code spans first
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # links: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: f'<a href="{link_target(m.group(2))}">{m.group(1)}</a>',
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def link_target(url: str) -> str:
    if url.startswith("http") or url.startswith("#"):
        return url
    absolute = False
    if url.startswith("/api-reference/"):
        absolute = True
        url = url[len("/api-reference/") :]
    if url.startswith("./"):
        url = url[2:]
    if url.endswith(".mdx"):
        url = url[:-4] + ".html"
    elif url.endswith(".md"):
        url = url[:-3] + ".html"
    elif "." not in url.rsplit("/", 1)[-1]:
        url += ".html"
    return ("/" + url) if absolute else url


def parse_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    fm = {}
    body = text
    if m:
        for line in m.group(1).splitlines():
            kv = re.match(r"^([A-Za-z_-]+):\s*\"?(.*?)\"?\s*$", line)
            if kv:
                fm[kv.group(1)] = kv.group(2).strip().strip('"')
        body = text[m.end() :]
    return fm, body


class Converter:
    def __init__(self, src_dir: str):
        self.src_dir = src_dir
        self.blocks: list[tuple[str, str]] = []  # (kind, html)

    def reserve(self, kind: str, html_: str) -> str:
        idx = len(self.blocks)
        self.blocks.append((kind, html_))
        return f"@@BLOCK{idx}@@"

    def convert(self, body: str) -> str:
        self.blocks = []
        body = self.extract_fences(body)
        body = self.extract_components(body)
        html_ = self.markdown(body)
        # iterative reinsertion: nested placeholders (e.g. <Tip> inside a
        # <Step> inside <Steps>) are expanded in later passes
        for _ in range(len(self.blocks) + 2):
            prev = html_
            html_ = re.sub(
                r"@@BLOCK(\d+)@@", lambda m: self.blocks[int(m.group(1))][1], html_
            )
            if html_ == prev:
                break
        return html_

    # ---------- fenced code blocks ----------
    def extract_fences(self, body: str) -> str:
        def repl(m):
            lang = m.group(1).split()[0] if m.group(1) else ""
            code = m.group(2).strip("\n")
            label = ""
            if lang and lang != "text":
                label = f'<span class="code-lang">{esc(lang)}</span>'
            out = (
                f'<div class="codeblock">{label}'
                f"<pre><code>{esc(code)}</code></pre></div>"
            )
            return self.reserve("code", out)

        return re.sub(r"```([^\n]*)\n(.*?)```", repl, body, flags=re.S)

    # ---------- Mintlify components ----------
    def extract_components(self, body: str) -> str:
        def wrap(name, inner, cls):
            return self.reserve(name, f'<div class="{cls}">{inner}</div>')

        # <Info>/<Tip>/<Note>/<Warning> admonitions
        def admo(m):
            kind, inner = m.group(1), m.group(2).strip()
            return wrap(
                kind,
                f'<p class="admo-label">{esc(kind)}</p>{self.markdown(inner)}',
                f"admo admo-{kind.lower()}",
            )

        body = re.sub(r"<(Info|Tip|Note|Warning)>([\s\S]*?)</\1>", admo, body)

        # <CodeGroup> — fences inside were already extracted; drop the wrapper
        body = re.sub(r"</?CodeGroup>", "", body)

        # <Steps> with <Step title="..."> items -> <ol class="steps">
        def steps(m):
            inner = m.group(1)
            items = []
            for sm in re.finditer(r'<Step\s+title="([^"]*)">([\s\S]*?)</Step>', inner):
                title, content = sm.group(1), sm.group(2).strip()
                body_html = self.markdown(content)
                if not re.search(r"<(p|ul|ol|div|pre)\b", body_html):
                    body_html = f"<p>{body_html}</p>"
                items.append(f"<li><strong>{esc(title)}</strong>{body_html}</li>")
            return self.reserve("steps", f'<ol class="steps">{"".join(items)}</ol>')

        body = re.sub(r"<Steps>([\s\S]*?)</Steps>", steps, body)

        # <RequestExample>/<ResponseExample> containing one fenced code block
        def example(m):
            kind = m.group(1)
            inner = m.group(2)
            fence = re.search(r"```([^\n]*)\n(.*?)```", inner, re.S)
            if fence:
                lang = fence.group(1).split()[0]
                code = fence.group(2).strip("\n")
                label = "Request" if kind == "RequestExample" else "Response"
                label_html = f'<span class="code-lang">{esc(label)}</span>'
                if lang and lang != "bash":
                    label_html += f'<span class="code-lang">{esc(lang)}</span>'
                return self.reserve(
                    kind,
                    f'<div class="codeblock">{label_html}<pre><code>{esc(code)}</code></pre></div>',
                )
            return self.reserve(kind, "")

        body = re.sub(
            r"<(RequestExample|ResponseExample)>([\s\S]*?)</\1>", example, body
        )

        PARAM_RE = r'<ParamField\s+(?:path|body)="([^"]+)"\s+type="([^"]*)"([^>]*)>([\s\S]*?)</ParamField>'
        RESPFIELD_RE = r'<ResponseField\s+name="([^"]+)"\s+type="([^"]*)"[^>]*>([\s\S]*?)</ResponseField>'

        # <ParamField path|body="..." type="..." required default="...">...</ParamField>
        def paramfield(m):
            path = m.group(1)
            type_ = m.group(2) or ""
            attrs = m.group(3)
            required = " required" if "required" in attrs else ""
            default = ""
            dm = re.search(r'default="([^"]*)"', attrs)
            if dm:
                default = (
                    f'<span class="param-default">default: {esc(dm.group(1))}</span>'
                )
            desc = self.markdown(m.group(4).strip())
            return self.reserve(
                "paramfield",
                f'<div class="paramfield"><span class="param-name">{esc(path)}</span>'
                f'<span class="param-type">{esc(type_)}{required}</span>{default}'
                f'<div class="param-desc">{desc}</div></div>',
            )

        # <ResponseField name="..." type="...">...</ResponseField>
        def respfield(m):
            name = m.group(1)
            type_ = m.group(2) or ""
            desc = self.markdown(m.group(3).strip())
            return self.reserve(
                "respfield",
                f'<div class="respfield"><span class="param-name">{esc(name)}</span>'
                f'<span class="param-type">{esc(type_)}</span><div class="param-desc">{desc}</div></div>',
            )

        # <Expandable title="...">...</Expandable> — processed BEFORE the
        # standalone param/resp fields so nested ones (invalid but present in
        # the docs) don't truncate the outer match
        def expandable(m):
            title = m.group(1)
            content = re.sub(PARAM_RE, paramfield, m.group(2))
            content = re.sub(RESPFIELD_RE, respfield, content)
            content = self.markdown(content.strip())
            return self.reserve(
                "expandable",
                f'<details class="expandable"><summary>{esc(title)}</summary>{content}</details>',
            )

        body = re.sub(
            r'<Expandable\s+title="([^"]*)">([\s\S]*?)</Expandable>',
            expandable,
            body,
        )

        # <AccordionGroup> with <Accordion title="..."> items -> <details> blocks
        def accordion(m):
            content = re.sub(PARAM_RE, paramfield, m.group(2))
            content = re.sub(RESPFIELD_RE, respfield, content)
            content = self.markdown(content.strip())
            return self.reserve(
                "accordion",
                f'<details class="expandable"><summary>{esc(m.group(1))}</summary>{content}</details>',
            )

        body = re.sub(
            r'<Accordion\s+title="([^"]*)">([\s\S]*?)</Accordion>', accordion, body
        )
        body = re.sub(r"</?AccordionGroup>", "", body)

        body = re.sub(PARAM_RE, paramfield, body)
        body = re.sub(RESPFIELD_RE, respfield, body)

        return body

    # ---------- markdown ----------
    def markdown(self, text: str) -> str:
        lines = text.split("\n")
        out = []
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]

            if line.strip() == "":
                i += 1
                continue

            # placeholder re-inserted later; keep as-is
            m = re.match(r"^@@BLOCK\d+@@$", line.strip())
            if m:
                out.append(line.strip())
                i += 1
                continue

            # headings (# -> h1 .. #### -> h4; the page title is rendered
            # separately as the page h1, and strip_title_h1() removes any
            # duplicate "# Title" line)
            m = re.match(r"^(#{1,4})\s+(.*)$", line)
            if m:
                level = min(len(m.group(1)), 4)
                out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
                i += 1
                continue

            # fenced block (raw, if not extracted)
            if line.startswith("```"):
                lang = line[3:].strip().split()[0] if line[3:].strip() else ""
                buf = []
                i += 1
                while i < n and not lines[i].startswith("```"):
                    buf.append(lines[i])
                    i += 1
                i += 1
                out.append(
                    f'<div class="codeblock">{f'<span class="code-lang">{esc(lang)}</span>' if lang and lang != "text" else ""}<pre><code>{esc(chr(10).join(buf))}</code></pre></div>'
                )
                continue

            # hr
            if re.match(r"^-{3,}$", line.strip()):
                out.append("<hr>")
                i += 1
                continue

            # table
            if line.lstrip().startswith("|"):
                tbl = []
                while i < n and lines[i].lstrip().startswith("|"):
                    tbl.append(lines[i].strip())
                    i += 1
                out.append(self.table(tbl))
                continue

            # list
            if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
                items = []
                while i < n:
                    m2 = re.match(r"^\s*([-*+]|\d+\.)\s+(.*)$", lines[i])
                    if not m2:
                        break
                    items.append(m2.group(2))
                    i += 1
                tag = "ol" if re.match(r"^\s*\d+\.\s+", lines[i - len(items)]) else "ul"
                out.append(
                    f"<{tag}>"
                    + "".join(f"<li>{inline(it)}</li>" for it in items)
                    + f"</{tag}>"
                )
                continue

            # blockquote
            if line.startswith(">"):
                buf = []
                while i < n and lines[i].startswith(">"):
                    buf.append(lines[i][1:].strip())
                    i += 1
                out.append(f"<blockquote>{inline(' '.join(buf))}</blockquote>")
                continue

            # paragraph (until blank or block start)
            buf = [line]
            i += 1
            while (
                i < n
                and lines[i].strip() != ""
                and not lines[i].startswith(("#", "|", "```", ">", "-", "*", "+", "1."))
            ):
                if re.match(r"^@@BLOCK\d+@@$", lines[i].strip()):
                    break
                buf.append(lines[i])
                i += 1
            out.append(f"<p>{inline(' '.join(buf))}</p>")

        return "\n".join(out)

    def table(self, rows):
        def cells(r):
            return [c.strip() for c in r.strip().strip("|").split("|")]

        head = cells(rows[0])
        body_rows = []
        for r in rows[2:]:
            body_rows.append(cells(r))
        thead = "".join(f"<th>{inline(h)}</th>" for h in head)
        trs = []
        for br in body_rows:
            tds = "".join(f"<td>{inline(c)}</td>" for c in br)
            trs.append(f"<tr>{tds}</tr>")
        return f'<div class="table-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'


def slug_from_path(path: Path, rel: Path) -> str:
    return path.parent.name + "/" + path.stem if path.parent != rel else path.stem


def strip_title_h1(title: str, body: str) -> str:
    """Drop a leading `# Title` line that duplicates the page title."""
    m = re.match(r"^#\s+(.*)$", body, re.M)
    if m and m.group(1).strip().lower() == title.lower():
        body = body[m.end() :].lstrip()
    return body


# ---------- heading ids + on-this-page TOC ----------


def add_heading_ids(content: str) -> str:
    """Add slug ids + "#" anchor links to h2/h3/h4 headings."""
    used: dict[str, int] = {}

    def repl(m):
        level = m.group(1)
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "section"
        n = used.get(slug, 0)
        used[slug] = n + 1
        if n:
            slug = f"{slug}-{n + 1}"
        return (
            f'<h{level} id="{slug}">'
            f'<a class="anchor" href="#{slug}" aria-hidden="true" tabindex="-1">#</a>'
            f"{m.group(2)}</h{level}>"
        )

    return re.sub(r"<h([234])>(.*?)</h\1>", repl, content)


def extract_toc(content: str) -> list[tuple[int, str, str]]:
    """Collect (level, id, text) for h2/h3 headings."""
    items = []
    for m in re.finditer(r'<h([23]) id="([^"]+)">(.*?)</h\1>', content):
        text = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        items.append((int(m.group(1)), m.group(2), text))
    return items


def nav_lookup() -> dict[str, tuple[str, str]]:
    """href -> (group, label)"""
    return {href: (group, label) for group, items in NAV for label, href in items}


def render_page(
    title: str,
    description: str,
    content: str,
    current: str,
    prev: tuple[str, str] | None = None,
    next_: tuple[str, str] | None = None,
) -> str:
    lookup = nav_lookup()
    group, label = lookup.get(current, ("", title))

    # ---------- sidebar ----------
    nav_html = []
    for grp, items in NAV:
        lis = []
        for lbl, href in items:
            cls = ' class="active"' if href == current else ""
            lis.append(f'<li><a href="/{href}"{cls}>{esc(lbl)}</a></li>')
        nav_html.append(
            f'<div class="nav-group"><div class="nav-group-title">{esc(grp)}</div><ul>{"".join(lis)}</ul></div>'
        )

    # ---------- topbar links ----------
    guides = current.startswith(("computed-variables", "embedding"))
    topnav = [
        ('<a href="/" class="active">API Reference</a>')
        if not guides
        else '<a href="/">API Reference</a>',
        ('<a href="/computed-variables.html" class="active">Guides</a>')
        if guides
        else '<a href="/computed-variables.html">Guides</a>',
        '<a href="https://sharaforms.com" class="topnav-ext">Website ↗</a>',
    ]

    # ---------- breadcrumbs ----------
    crumbs = '<a href="/">Home</a>'
    if current != "index.html":
        if group and group != "Overview":
            crumbs += f'<span class="crumb-sep">/</span><span class="crumb-static">{esc(group)}</span>'
        crumbs += f'<span class="crumb-sep">/</span><span class="crumb-current">{esc(label or title)}</span>'
    breadcrumbs = f'<nav class="breadcrumbs" aria-label="Breadcrumb">{crumbs}</nav>'

    # ---------- on-this-page TOC ----------
    toc_items = extract_toc(content)
    toc_html = ""
    if len(toc_items) >= 2:
        lis = []
        for level, hid, text in toc_items:
            lis.append(
                f'<li class="toc-l{level}"><a href="#{hid}">{esc(text)}</a></li>'
            )
        toc_html = (
            f'<aside class="toc" aria-label="On this page">'
            f'<div class="toc-title">On this page</div>'
            f"<ul>{''.join(lis)}</ul></aside>"
        )

    # ---------- pager ----------
    pager = ""
    if prev or next_:
        parts = []
        if prev:
            parts.append(
                f'<a class="page-nav prev" href="/{prev[1]}"><span class="page-nav-label">← Previous</span>{esc(prev[0])}</a>'
            )
        if next_:
            parts.append(
                f'<a class="page-nav next" href="/{next_[1]}"><span class="page-nav-label">Next →</span>{esc(next_[0])}</a>'
            )
        pager = f'<div class="pager">{"".join(parts)}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {SITE_NAME}</title>
<meta name="description" content="{esc(description)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{SITE_URL}/{current}">
<link rel="stylesheet" href="/styles.css">
<link rel="icon" href="data:,">
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<input type="checkbox" id="nav-toggle" class="nav-toggle" aria-hidden="true">
<header class="topbar">
  <label class="nav-burger" for="nav-toggle" aria-label="Toggle navigation"><span></span></label>
  <a class="brand" href="/"><span class="brand-mark">S</span><span class="brand-name">SharaForms</span><span class="brand-sub">Docs</span></a>
  <nav class="topnav" aria-label="Site">{"".join(topnav)}</nav>
</header>
<label class="scrim" for="nav-toggle" aria-hidden="true"></label>
<div class="layout">
  <nav class="sidebar" aria-label="Documentation">{"".join(nav_html)}</nav>
  <main class="content" id="content">
    {breadcrumbs}
    <article>
      <h1 class="page-title">{esc(title)}</h1>
      {content}
    </article>
    {pager}
    <footer class="footer">
      <span class="footer-copy">© 2026 SharaForms</span>
      <span class="footer-links">
        <a href="https://sharaforms.com">sharaforms.com</a>
        <a href="https://github.com/FFFSTANZA/sharaforms">GitHub</a>
      </span>
      <span class="footer-base">Base URL <code>{BASE_URL}</code></span>
    </footer>
  </main>
  {toc_html}
</div>
</body>
</html>
"""


CSS = """:root{
  --accent:#4f46e5;            /* indigo-600 */
  --accent-weak:#eef2ff;
  --accent-strong:#4338ca;
  --text:#0f172a;              /* slate-900 */
  --muted:#64748b;             /* slate-500 */
  --border:#e2e8f0;            /* slate-200 */
  --bg:#ffffff;
  --bg-subtle:#f8fafc;         /* slate-50 */
  --bg-hover:#f1f5f9;          /* slate-100 */
  --code-bg:#0f172a;           /* slate-900 */
  --code-bar:#1e293b;          /* slate-800 */
  --code-text:#e2e8f0;
  --code-inline-bg:#f1f5f9;
  --radius:10px;
  --shadow-sm:0 1px 2px rgb(15 23 42 / .05);
  --shadow-md:0 8px 24px rgb(15 23 42 / .08);
  --topbar-h:56px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  color:var(--text);line-height:1.7;background:var(--bg);font-size:16px;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
}
::selection{background:var(--accent);color:#fff}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}

/* ---------- topbar ---------- */
.topbar{
  position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:20px;
  height:var(--topbar-h);padding:0 24px;
  background:rgb(255 255 255 / .85);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border-bottom:1px solid var(--border);
}
.brand{display:flex;align-items:center;gap:9px;color:var(--text);font-weight:800;font-size:15px;letter-spacing:-.01em}
.brand:hover{text-decoration:none}
.brand-mark{
  display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:7px;
  background:linear-gradient(135deg,var(--accent),#7c3aed);color:#fff;font-size:15px;font-weight:800;
  box-shadow:var(--shadow-sm);
}
.brand-name{white-space:nowrap}
.brand-sub{color:var(--muted);font-weight:500}
.topnav{display:flex;align-items:center;gap:4px;margin-left:auto}
.topnav a{padding:6px 12px;border-radius:8px;font-size:14px;font-weight:500;color:var(--muted)}
.topnav a:hover{background:var(--bg-hover);color:var(--text);text-decoration:none}
.topnav a.active{color:var(--accent);background:var(--accent-weak);font-weight:600}
.nav-burger{display:none;cursor:pointer;width:38px;height:38px;border-radius:8px;align-items:center;justify-content:center}
.nav-burger:hover{background:var(--bg-hover)}
.nav-burger span,.nav-burger span::before,.nav-burger span::after{
  display:block;width:18px;height:2px;border-radius:2px;background:var(--text);position:relative;
}
.nav-burger span::before{content:"";position:absolute;top:-6px}
.nav-burger span::after{content:"";position:absolute;top:6px}
.nav-toggle{position:absolute;opacity:0;pointer-events:none}
.scrim{display:none}

/* ---------- layout ---------- */
.layout{
  display:grid;grid-template-columns:264px minmax(0,1fr) 232px;
  max-width:1440px;margin:0 auto;
}
.sidebar{
  position:sticky;top:var(--topbar-h);height:calc(100vh - var(--topbar-h));overflow-y:auto;
  border-right:1px solid var(--border);padding:28px 14px 48px;
}
.content{min-width:0;padding:40px 56px 96px;max-width:880px}
.toc{position:sticky;top:var(--topbar-h);height:calc(100vh - var(--topbar-h));overflow-y:auto;padding:48px 20px 48px 12px;align-self:start}
.toc-title{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:12px}
.toc ul{list-style:none;display:flex;flex-direction:column;gap:2px}
.toc a{display:block;padding:4px 8px;border-radius:6px;font-size:13px;color:var(--muted);border-left:2px solid transparent}
.toc a:hover{background:var(--bg-hover);color:var(--text);text-decoration:none}
.toc-l2 a{font-weight:500;color:#334155}
.toc-l3 a{padding-left:20px;font-size:12.5px}

/* ---------- sidebar nav ---------- */
.nav-group{margin-bottom:22px}
.nav-group-title{
  font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);padding:0 10px;margin-bottom:6px;
}
.nav-group ul{list-style:none}
.nav-group li{margin:1px 0}
.nav-group a{
  display:block;padding:5px 10px;border-radius:7px;font-size:13.5px;color:#334155;
  line-height:1.45;
}
.nav-group a:hover{background:var(--bg-hover);color:var(--text);text-decoration:none}
.nav-group a.active{background:var(--accent-weak);color:var(--accent);font-weight:600}

/* ---------- breadcrumbs ---------- */
.breadcrumbs{display:flex;flex-wrap:wrap;align-items:center;gap:7px;font-size:13px;color:var(--muted);margin-bottom:18px}
.breadcrumbs a{color:var(--muted)}
.breadcrumbs a:hover{color:var(--accent);text-decoration:none}
.crumb-sep{color:#cbd5e1}
.crumb-static{color:var(--muted)}
.crumb-current{color:var(--text);font-weight:600}

/* ---------- typography ---------- */
.page-title{font-size:clamp(1.75rem,3.2vw,2.25rem);font-weight:800;letter-spacing:-.025em;line-height:1.2;margin:0 0 8px}
article > p:first-of-type{font-size:17px;color:#475569;margin-bottom:20px}
article h2{
  font-size:1.4rem;font-weight:700;letter-spacing:-.015em;margin:44px 0 14px;padding-top:10px;
  scroll-margin-top:calc(var(--topbar-h) + 20px);
}
article h3{
  font-size:1.12rem;font-weight:700;margin:30px 0 10px;
  scroll-margin-top:calc(var(--topbar-h) + 20px);
}
article h4{font-size:1rem;font-weight:700;margin:24px 0 8px;scroll-margin-top:calc(var(--topbar-h) + 20px)}
article p{margin:12px 0}
article ul,article ol{margin:12px 0 12px 26px}
article li{margin:5px 0}
article li > ul,article li > ol{margin:4px 0 4px 24px}
article li::marker{color:var(--accent)}
article a{font-weight:500}
.anchor{display:inline-block;width:0;margin-left:2px;color:#cbd5e1;font-weight:600;opacity:0;transition:opacity .15s}
article h2:hover .anchor,article h3:hover .anchor,article h4:hover .anchor{opacity:1}
.anchor:hover{color:var(--accent);text-decoration:none}
hr{border:none;border-top:1px solid var(--border);margin:32px 0}

/* ---------- code ---------- */
article code{
  font-size:.87em;background:var(--code-inline-bg);border:1px solid var(--border);
  border-radius:5px;padding:2px 6px;color:#312e81;
}
.codeblock{
  background:var(--code-bg);border-radius:var(--radius);margin:18px 0;overflow:hidden;
  box-shadow:var(--shadow-sm);
}
.codeblock .code-lang{
  display:inline-flex;align-items:center;height:34px;padding:0 14px;margin-right:8px;
  font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  color:#cbd5e1;background:var(--code-bar);
  border-bottom:1px solid #334155;border-right:1px solid #334155;border-radius:0 0 8px 0;
}
.codeblock pre{padding:16px 18px;margin:0;overflow-x:auto}
.codeblock pre code{
  display:block;background:transparent;border:none;padding:0;
  font-size:13px;line-height:1.65;white-space:pre;color:var(--code-text);
}

/* ---------- tables ---------- */
.table-wrap{
  margin:18px 0;border:1px solid var(--border);border-radius:var(--radius);
  overflow:hidden;overflow-x:auto;box-shadow:var(--shadow-sm);
}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:10px 16px;border-bottom:1px solid var(--border);vertical-align:top}
th{background:var(--bg-subtle);font-weight:600;white-space:nowrap;font-size:13px;letter-spacing:.01em}
td{color:#334155}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--bg-subtle)}
td code,th code{white-space:nowrap}

/* ---------- admonitions ---------- */
.admo{border:1px solid var(--border);border-left:4px solid var(--accent);border-radius:var(--radius);padding:14px 18px;margin:18px 0}
.admo p{margin:5px 0}
.admo .admo-label{display:flex;align-items:center;gap:6px;margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.admo .admo-label::before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor}
.admo-info{border-left-color:#2563eb;background:#eff6ff}
.admo-info .admo-label{color:#1d4ed8}
.admo-tip{border-left-color:#16a34a;background:#f0fdf4}
.admo-tip .admo-label{color:#15803d}
.admo-note{border-left-color:#d97706;background:#fffbeb}
.admo-note .admo-label{color:#b45309}
.admo-warning{border-left-color:#dc2626;background:#fef2f2}
.admo-warning .admo-label{color:#b91c1c}

/* ---------- steps ---------- */
ol.steps{list-style:none;counter-reset:step;margin:20px 0;padding:0}
ol.steps>li{
  counter-increment:step;position:relative;margin:0;padding:0 0 26px 46px;
}
ol.steps>li::before{
  content:counter(step);position:absolute;left:0;top:2px;width:30px;height:30px;border-radius:50%;
  background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:13.5px;box-shadow:var(--shadow-sm);
}
ol.steps>li:not(:last-child)::after{content:"";position:absolute;left:14.5px;top:38px;bottom:4px;width:1.5px;background:var(--border)}
ol.steps>li>strong{display:block;font-size:15.5px;margin-bottom:4px}
ol.steps>li>p{margin:4px 0}

/* ---------- expandables / param fields ---------- */
details.expandable{margin:12px 0;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;background:var(--bg-subtle)}
details.expandable summary{
  cursor:pointer;padding:12px 44px 12px 16px;font-weight:600;font-size:14.5px;
  position:relative;list-style:none;
}
details.expandable summary::-webkit-details-marker{display:none}
details.expandable summary::after{
  content:"";position:absolute;right:18px;top:50%;width:8px;height:8px;
  border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);
  transform:translateY(-70%) rotate(45deg);transition:transform .15s;
}
details.expandable[open] summary{border-bottom:1px solid var(--border)}
details.expandable[open] summary::after{transform:translateY(-30%) rotate(-135deg)}
details.expandable > *:not(summary){padding:12px 16px;background:var(--bg)}
details.expandable p{margin:6px 0}
blockquote{border-left:3px solid var(--border);padding:6px 18px;color:var(--muted);margin:16px 0;background:var(--bg-subtle);border-radius:0 var(--radius) var(--radius) 0}
.paramfield,.respfield{margin:10px 0;padding:12px 16px;border:1px solid var(--border);border-radius:var(--radius);background:var(--bg-subtle)}
.param-name{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13.5px;font-weight:700;color:var(--accent-strong)}
.param-type{
  display:inline-block;margin-left:8px;font-size:11.5px;color:var(--muted);background:#fff;
  border:1px solid var(--border);border-radius:5px;padding:1px 7px;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;vertical-align:1px;
}
.param-type.required{color:#b91c1c;border-color:#fecaca;background:#fef2f2}
.param-default{display:inline-block;margin-left:8px;font-size:11.5px;color:var(--muted);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.param-desc{margin-top:5px;font-size:14px;color:#334155}
.param-desc p{margin:4px 0}
.paramfield .paramfield,.respfield .paramfield{margin-left:16px}

/* ---------- pager ---------- */
.pager{
  display:flex;justify-content:space-between;gap:16px;margin-top:56px;padding-top:28px;
  border-top:1px solid var(--border);
}
.page-nav{
  flex:1;display:block;border:1px solid var(--border);border-radius:var(--radius);
  padding:14px 18px;color:var(--text);font-weight:600;font-size:14.5px;
  background:var(--bg);transition:border-color .15s,box-shadow .15s;
}
.page-nav:hover{border-color:var(--accent);text-decoration:none;box-shadow:var(--shadow-sm)}
.page-nav-label{display:block;font-size:12px;color:var(--muted);font-weight:500;margin-bottom:3px}
.page-nav.next{text-align:right}

/* ---------- footer ---------- */
.footer{
  margin-top:64px;padding-top:24px;border-top:1px solid var(--border);
  display:flex;flex-wrap:wrap;align-items:center;gap:12px 24px;
  font-size:13px;color:var(--muted);
}
.footer-links{display:flex;gap:18px}
.footer-links a{color:var(--muted)}
.footer-links a:hover{color:var(--accent);text-decoration:none}
.footer-base code{font-size:12px}

/* ---------- skip link ---------- */
.skip{position:absolute;left:-9999px;top:0;z-index:100;background:var(--accent);color:#fff;padding:8px 16px;border-radius:0 0 8px 0;font-weight:600}
.skip:focus{left:0}

/* ---------- responsive ---------- */
@media (max-width:1180px){
  .layout{grid-template-columns:250px minmax(0,1fr)}
  .toc{display:none}
  .content{padding:36px 40px 88px}
}
@media (max-width:900px){
  .topnav{display:none}
  .nav-burger{display:inline-flex}
  .layout{display:block}
  .sidebar{
    position:fixed;top:var(--topbar-h);left:0;bottom:0;z-index:40;
    width:min(320px,86vw);height:auto;background:var(--bg);
    box-shadow:var(--shadow-md);border-right:1px solid var(--border);
    transform:translateX(-105%);transition:transform .22s ease;
  }
  .nav-toggle:checked ~ .layout .sidebar{transform:translateX(0)}
  .nav-toggle:checked ~ .layout .scrim,
  .nav-toggle:checked ~ .scrim{display:block}
  .scrim{
    position:fixed;inset:var(--topbar-h) 0 0 0;z-index:35;background:rgb(15 23 42 / .45);
  }
  .content{padding:28px 22px 80px;max-width:none}
  .page-title{font-size:1.6rem}
  article > p:first-of-type{font-size:16px}
  .pager{flex-direction:column}
  .page-nav{width:100%}
  .footer{flex-direction:column;align-items:flex-start;gap:8px}
}
"""


def flatten_nav():
    return [(label, href) for _g, items in NAV for label, href in items]


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "forms").mkdir(parents=True)
    for d in (
        "submissions",
        "integrations",
        "workspaces",
        "workspace-users",
        "embedding",
    ):
        (OUT / d).mkdir(parents=True)
    (OUT / "styles.css").write_text(CSS)

    # GitHub Pages deployment files (docs-repo mode)
    if OUT != ROOT / "site":
        (OUT / "CNAME").write_text("docs.sharaforms.com\n")
        (OUT / ".nojekyll").touch()

    flat = flatten_nav()
    pages: dict[str, str] = {}

    conv = Converter(str(MDX_DIR))

    # --- mdx-based pages ---
    for mdx in sorted(MDX_DIR.rglob("*.mdx")):
        if mdx.parent.name == "images" or mdx.parent.name == "endpoint":
            continue  # legacy endpoint stubs not in live docs
        if mdx.parent.name == "zapier":
            continue  # legacy Zapier pages not in the minimal docs
        fm, body = parse_frontmatter(mdx.read_text())
        if "openapi" in fm and not any(c in body for c in ("##", "# ")):
            continue
        m = re.match(r"^#\s+(.*)$", body, re.M)
        title = fm.get("title") or (m.group(1) if m else mdx.stem)
        desc = fm.get("description", f"{title} — SharaForms API reference.")
        body = strip_title_h1(title, body)
        if mdx.parent != MDX_DIR:
            key = f"{mdx.parent.name}/{mdx.stem}.html"
        else:
            key = "index.html" if mdx.stem == "introduction" else f"{mdx.stem}.html"
        content = add_heading_ids(conv.convert(body))
        pages[key] = content
        print(f"built {key} ({title})")

    # --- extra guide pages (computed variables, embedding) ---
    for key, mdx_path in EXTRA_SOURCES:
        fm, body = parse_frontmatter(mdx_path.read_text())
        title = fm.get("title") or mdx_path.stem
        desc = fm.get("description", f"{title} — SharaForms guide.")
        body = strip_title_h1(title, body)
        content = add_heading_ids(conv.convert(body))
        pages[key + ".html"] = content
        print(f"built {key}.html ({title})")

    # --- render + pager wiring ---
    rendered: dict[str, str] = {}
    meta: dict[str, tuple[str, str]] = {}
    for mdx in sorted(MDX_DIR.rglob("*.mdx")):
        if mdx.parent.name in ("images", "endpoint", "zapier"):
            continue
        fm, body = parse_frontmatter(mdx.read_text())
        if "openapi" in fm and not any(c in body for c in ("##", "# ")):
            continue
        title = fm.get("title") or mdx.stem
        desc = fm.get("description", f"{title} — SharaForms API reference.")
        if mdx.parent != MDX_DIR:
            key = f"{mdx.parent.name}/{mdx.stem}.html"
        else:
            key = "index.html" if mdx.stem == "introduction" else f"{mdx.stem}.html"
        meta[key] = (title, desc)
    for key, mdx_path in EXTRA_SOURCES:
        fm, body = parse_frontmatter(mdx_path.read_text())
        title = fm.get("title") or mdx_path.stem
        desc = fm.get("description", f"{title} — SharaForms guide.")
        meta[key + ".html"] = (title, desc)

    for key, content in pages.items():
        title, desc = meta.get(key, (key, key))
        prev = next_ = None
        for i, (label, href) in enumerate(flat):
            if href == key:
                prev = flat[i - 1] if i > 0 else None
                next_ = flat[i + 1] if i + 1 < len(flat) else None
                prev = prev if prev and prev[1] in pages else None
                next_ = next_ if next_ and next_[1] in pages else None
                break
        rendered[key] = render_page(title, desc, content, key, prev, next_)

    for key, html_ in rendered.items():
        out_path = OUT / key
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_)

    # --- sitemap + 404 ---
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    )
    for key in sorted(rendered):
        sitemap += f"  <url><loc>{SITE_URL}/{key}</loc></url>\n"
    sitemap += "</urlset>\n"
    (OUT / "sitemap.xml").write_text(sitemap)

    (OUT / "404.html").write_text(
        render_page(
            "Page not found",
            "The page you're looking for doesn't exist.",
            '<p>The page you are looking for does not exist or has moved.</p><p><a href="/">← Back to documentation home</a></p>',
            "404.html",
        )
    )

    count = len(list(OUT.rglob("*.html")))
    print(f"\nDone. {count} HTML pages written to {OUT}")


if __name__ == "__main__":
    sys.exit(main())
