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
OUT = ROOT / "site"

SITE_NAME = "SharaForms API Docs"
BASE_URL = "https://api.sharaforms.com"

NAV = [
    (
        "Overview",
        [
            ("Introduction", "index.html"),
            ("API Keys", "api-keys.html"),
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
        ],
    ),
]

EXTRA_SOURCES = [
    (
        "computed-variables",
        ROOT.parent / "docs" / "features" / "computed-variables.mdx",
    ),
    (
        "embedding/javascript-sdk",
        ROOT.parent / "docs" / "embedding" / "javascript-sdk.mdx",
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
                items.append(f"<li><strong>{esc(title)}.</strong> {body_html}</li>")
            return self.reserve("steps", f'<ol class="steps">{"".join(items)}</ol>')

        body = re.sub(r"<Steps>([\s\S]*?)</Steps>", steps, body)

        # <Frame><img .../></Frame>
        def frame(m):
            img = re.search(
                r"<img\s+src=\"([^\"]+)\"\s*(?:alt=\"([^\"]*)\")?\s*/?>", m.group(1)
            )
            if not img:
                return self.reserve("frame", "")
            src = img.group(1)
            if src.startswith("/api-reference/"):
                src = src[len("/api-reference/") :]
            return self.reserve(
                "frame",
                f'<figure class="frame"><img src="{src}" alt="{esc(img.group(2) or "")}" loading="lazy"></figure>',
            )

        body = re.sub(r"<Frame>([\s\S]*?)</Frame>", frame, body)

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

        # <Steps>…</Steps> -> <ol class="steps"> (handled above; remove leftovers)

        # leftover raw tags safety
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

            # headings
            m = re.match(r"^(#{1,4})\s+(.*)$", line)
            if m:
                level = min(len(m.group(1)) + 1, 6)  # h1 -> h1, h2 -> h2 ...
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
                ordered = re.match(
                    r"^\s*\d+\.\s+", lines[i - 1] if i <= n else ""
                ) is not None or any(re.match(r"^\d+\.\s", it) for it in items if False)
                ordered = False
                # detect order from first item
                if re.match(r"^\s*\d+\.\s+", lines[i - len(items)]) and False:
                    ordered = True
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


def render_page(
    title: str,
    description: str,
    content: str,
    current: str,
    prev: str | None = None,
    next_: str | None = None,
) -> str:
    nav_html = []
    for group, items in NAV:
        lis = []
        for label, href in items:
            cls = ' class="active"' if href == current else ""
            lis.append(f'<li><a href="/{href}"{cls}>{esc(label)}</a></li>')
        nav_html.append(
            f'<div class="nav-group"><div class="nav-group-title">{esc(group)}</div><ul>{"".join(lis)}</ul></div>'
        )
    pager = ""
    if prev or next_:
        parts = []
        if prev:
            parts.append(
                f'<a class="page-nav prev" href="/{prev[1]}"><span>Previous</span>{esc(prev[0])}</a>'
            )
        if next_:
            parts.append(
                f'<a class="page-nav next" href="/{next_[1]}"><span>Next</span>{esc(next_[0])}</a>'
            )
        pager = f'<div class="pager">{"".join(parts)}</div>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {SITE_NAME}</title>
<meta name="description" content="{esc(description)}">
<link rel="stylesheet" href="/styles.css">
<link rel="icon" href="data:,">
</head>
<body>
<header class="topbar">
  <a class="brand" href="/"><span class="brand-mark">S</span> SharaForms <span class="brand-sub">API Docs</span></a>
  <a class="topbar-link" href="https://sharaforms.com">sharaforms.com ↗</a>
</header>
<div class="layout">
  <nav class="sidebar">{"".join(nav_html)}</nav>
  <main class="content">
    <article>
      <h1 class="page-title">{esc(title)}</h1>
      {content}
    </article>
    {pager}
    <footer class="footer">SharaForms API Docs — base URL <code>{BASE_URL}</code></footer>
  </main>
</div>
</body>
</html>
"""


CSS = """:root{--accent:#3b82f6;--text:#1a1a1a;--muted:#6b7280;--border:#e5e7eb;--bg:#ffffff;--code-bg:#f6f8fa;--sidebar-bg:#fafafa}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;color:var(--text);line-height:1.65;background:var(--bg);font-size:16px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.topbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between;height:56px;padding:0 24px;background:var(--bg);border-bottom:1px solid var(--border)}
.brand{font-weight:700;font-size:15px;color:var(--text);display:flex;align-items:center;gap:8px}
.brand-mark{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:6px;background:var(--accent);color:#fff;font-size:14px;font-weight:700}
.brand-sub{color:var(--muted);font-weight:400}
.topbar-link{font-size:14px}
.layout{display:flex;max-width:1280px;margin:0 auto}
.sidebar{width:260px;flex-shrink:0;padding:24px 16px 48px;border-right:1px solid var(--border);background:var(--sidebar-bg);position:sticky;top:56px;height:calc(100vh - 56px);overflow-y:auto}
.nav-group{margin-bottom:20px}
.nav-group-title{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:0 8px;margin-bottom:6px}
.nav-group ul{list-style:none}
.nav-group li{margin:1px 0}
.nav-group a{display:block;padding:5px 8px;border-radius:6px;font-size:14px;color:#374151}
.nav-group a:hover{background:#f0f0f0;text-decoration:none}
.nav-group a.active{background:#e8f0fe;color:var(--accent);font-weight:600}
.content{flex:1;min-width:0;padding:40px 56px 80px;max-width:900px}
.page-title{font-size:32px;font-weight:800;letter-spacing:-.02em;margin-bottom:8px}
article h1{font-size:32px;font-weight:800;letter-spacing:-.02em;margin:0 0 16px}
article h2{font-size:22px;font-weight:700;margin:36px 0 12px;padding-top:8px}
article h3{font-size:17px;font-weight:700;margin:24px 0 8px}
article h4{font-size:15px;font-weight:700;margin:20px 0 6px}
article p{margin:10px 0}
article ul,article ol{margin:10px 0 10px 24px}
article li{margin:4px 0}
article code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.875em;background:var(--code-bg);border:1px solid var(--border);border-radius:4px;padding:1px 5px}
article pre{margin:12px 0}
article pre code{display:block;background:transparent;border:none;padding:0;font-size:13.5px;line-height:1.6;overflow-x:auto;white-space:pre}
.codeblock{background:var(--code-bg);border:1px solid var(--border);border-radius:8px;margin:14px 0;overflow:hidden}
.codeblock pre{padding:14px 16px;margin:0;overflow-x:auto}
.code-lang{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);background:var(--code-bg);border-bottom:1px solid var(--border);border-right:1px solid var(--border);padding:4px 10px;border-radius:8px 0 0 0}
.codeblock .code-lang:first-child{border-top:none}
.table-wrap{overflow-x:auto;margin:14px 0;border:1px solid var(--border);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:9px 14px;border-bottom:1px solid var(--border);vertical-align:top}
th{background:var(--sidebar-bg);font-weight:600;white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
td code,th code{white-space:nowrap}
.admo{border:1px solid var(--border);border-left:4px solid var(--accent);border-radius:8px;padding:12px 16px;margin:16px 0;background:#f8fafc}
.admo p{margin:4px 0}
.admo .admo-label{display:none}
.admo-info{border-left-color:#3b82f6}
.admo-tip{border-left-color:#22c55e}
.admo-note{border-left-color:#f59e0b}
.admo-warning{border-left-color:#ef4444}
ol.steps{list-style:none;counter-reset:step;margin:16px 0;padding:0}
ol.steps>li{counter-increment:step;margin:0 0 14px;padding:12px 14px;border:1px solid var(--border);border-radius:8px;background:var(--sidebar-bg)}
ol.steps>li>strong::before{content:counter(step) ". ";color:var(--accent)}
ol.steps>li>p{margin:4px 0}
details.expandable{margin:10px 0;border:1px solid var(--border);border-radius:8px;background:var(--sidebar-bg)}
details.expandable summary{cursor:pointer;padding:10px 14px;font-weight:600}
details.expandable[open] summary{border-bottom:1px solid var(--border)}
details.expandable .content-inner{padding:10px 14px}
.blockquote,blockquote{border-left:3px solid var(--border);padding:2px 16px;color:var(--muted);margin:14px 0;background:var(--sidebar-bg);border-radius:0 8px 8px 0}
.paramfield,.respfield{margin:10px 0;padding:10px 14px;border:1px solid var(--border);border-radius:8px;background:var(--sidebar-bg)}
.param-name{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13.5px;font-weight:600;color:var(--accent)}
.param-type{display:inline-block;margin-left:8px;font-size:12px;color:var(--muted);background:#fff;border:1px solid var(--border);border-radius:4px;padding:0 6px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.param-desc{margin-top:4px;font-size:14.5px}
.param-desc p{margin:4px 0}
.frame{margin:16px 0}
.frame img{max-width:100%;border:1px solid var(--border);border-radius:8px}
hr{border:none;border-top:1px solid var(--border);margin:28px 0}
.pager{display:flex;justify-content:space-between;gap:16px;margin-top:48px;padding-top:24px;border-top:1px solid var(--border)}
.page-nav{flex:1;display:block;border:1px solid var(--border);border-radius:8px;padding:12px 16px;color:var(--text);font-weight:600;font-size:14px}
.page-nav:hover{background:var(--sidebar-bg);text-decoration:none}
.page-nav span{display:block;font-size:12px;color:var(--muted);font-weight:400}
.page-nav.next{text-align:right}
.footer{margin-top:40px;font-size:13px;color:var(--muted)}
@media (max-width:860px){.layout{flex-direction:column}.sidebar{position:static;width:100%;height:auto;border-right:none;border-bottom:1px solid var(--border)}.content{padding:24px 20px 60px}.page-title{font-size:26px}}
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

    # copy images (create-token.png etc.)
    img_src = MDX_DIR / "images"
    if img_src.exists():
        shutil.copytree(img_src, OUT / "images")

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
        title = fm.get("title") or (
            re.match(r"^#\s+(.*)$", body, re.M).group(1)
            if re.match(r"^#\s+(.*)$", body, re.M)
            else mdx.stem
        )
        desc = fm.get("description", f"{title} — SharaForms API reference.")
        body = strip_title_h1(title, body)
        if mdx.parent != MDX_DIR:
            key = f"{mdx.parent.name}/{mdx.stem}.html"
        else:
            key = "index.html" if mdx.stem == "introduction" else f"{mdx.stem}.html"
        content = conv.convert(body)
        pages[key] = render_page(title, desc, content, key)
        print(f"built {key} ({title})")

    # --- extra guide pages (computed variables, embedding) ---
    for key, mdx_path in EXTRA_SOURCES:
        fm, body = parse_frontmatter(mdx_path.read_text())
        title = fm.get("title") or mdx_path.stem
        desc = fm.get("description", f"{title} — SharaForms guide.")
        body = strip_title_h1(title, body)
        content = conv.convert(body)
        pages[key + ".html"] = render_page(title, desc, content, key + ".html")
        print(f"built {key}.html ({title})")

    # --- pager wiring + write ---
    for i, (label, href) in enumerate(flat):
        if href not in pages:
            continue
        prev = flat[i - 1] if i > 0 else None
        nxt = flat[i + 1] if i + 1 < len(flat) else None
        prev = prev if prev and prev[1] in pages else None
        nxt = nxt if nxt and nxt[1] in pages else None
        html_ = pages[href]
        html_ = html_.replace(
            "</main>",
            f'<div class="pager">'
            f"{'<a class="page-nav prev" href="/' + prev[1] + '"><span>Previous</span>' + esc(prev[0]) + '</a>' if prev else ''}"
            f"{'<a class="page-nav next" href="/' + nxt[1] + '"><span>Next</span>' + esc(nxt[0]) + '</a>' if nxt else ''}"
            f"</div></main>",
        )
        out_path = OUT / href
        out_path.write_text(html_)

    # ensure index.html exists (introduction maps there)
    if "index.html" not in pages and Path(OUT / "introduction.html").exists():
        shutil.move(OUT / "introduction.html", OUT / "index.html")

    count = len(list(OUT.rglob("*.html")))
    print(f"\nDone. {count} HTML pages written to {OUT}")


if __name__ == "__main__":
    sys.exit(main())
