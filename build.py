#!/usr/bin/env python3
"""Build the Meritocratic Humanist site from logs/*/log.md into _site/.

    python build.py            # what the public site shows right now
    python build.py --preview  # also include scheduled and draft Logs (local check only)

Visibility per Log (front matter `status`):
    published  -> always shown
    scheduled  -> shown once `scheduled` (UTC, e.g. 2026-10-06T13:00:00Z) has passed
    draft      -> never shown
"""
import html
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from string import Template

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_site"
MAX_IMG = 1200  # px, longest side; smaller copies are kinder to fair use and to phones
NOW = datetime.now(timezone.utc)
PREVIEW = "--preview" in sys.argv

SITE = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8"))
TAGLINE_LINES = SITE["tagline"] if isinstance(SITE["tagline"], list) else [SITE["tagline"]]
TAGLINE = " ".join(TAGLINE_LINES)
BASE = Template((ROOT / "templates/base.html").read_text(encoding="utf-8"))
URL_RE = re.compile(r"(https?://[^\s<]+)")
TAG_RE = re.compile(r"(?<![\w&])(#\w+)")


# ---------- loading ----------

def read(path):
    raw = path.read_text(encoding="utf-8")
    _, fm, body = raw.split("---", 2)
    meta = yaml.safe_load(fm) or {}
    meta["body"] = body.strip()
    meta["dir"] = path.parent
    meta["id"] = path.parent.name  # folder name is the canonical id
    return meta


def parse_time(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def visible(log):
    status = log.get("status", "published")
    if PREVIEW or status == "published":
        return True
    if status == "scheduled":
        when = parse_time(log.get("scheduled"))
        return when is not None and when <= NOW
    return False


def load_logs():
    logs = []
    for f in sorted((ROOT / "logs").glob("*/log.md")):
        log = read(f)
        if not visible(log):
            continue
        supp = f.parent / "supplemental.md"
        log["supplemental"] = read(supp) if supp.exists() else None
        log["date"] = parse_time(log.get("published")) or parse_time(log.get("scheduled"))
        logs.append(log)
    logs.sort(key=lambda l: l["seq"])
    return logs


# ---------- rendering helpers ----------

def label(log):
    kind = "Special Log" if log.get("type") == "special" else "Log"
    num = log["id"][2:] if log["id"].startswith("SL") else log["id"]
    return f"{kind} {num}: {log['title']}"


def url(log):
    return f"/logs/{log['id']}/"


def text_to_html(text):
    """Blank line = new paragraph, single newline = line break. No Markdown surprises."""
    out = []
    for para in re.split(r"\n\s*\n", text.strip()):
        safe = html.escape(para, quote=False)
        safe = URL_RE.sub(r'<a href="\1">\1</a>', safe)
        safe = TAG_RE.sub(r'<span class="tag">\1</span>', safe)
        out.append("<p>" + safe.replace("\n", "<br>\n") + "</p>")
    return "\n".join(out)


def fmt_date(dt):
    return f"{dt.day} {dt:%B %Y}" if dt else ""


def excerpt(text, n=180):
    flat = " ".join(TAG_RE.sub("", text).split())
    return flat if len(flat) <= n else flat[: n - 1].rsplit(" ", 1)[0] + "…"


def e(s):
    return html.escape(str(s or ""), quote=True)


def page(path, title, content, description="", image="", canonical=""):
    og_img = f'<meta property="og:image" content="{e(SITE["base_url"] + image)}">' if image else ""
    doc = BASE.substitute(
        site=e(SITE["title"]),
        title=e(title),
        description=e(description or TAGLINE),
        icon_link=ICON_LINK,
        brand_icon=BRAND_ICON,
        canonical=e(SITE["base_url"] + canonical),
        og_image=og_img,
        links=links_html(),
        content=content,
    )
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")


def links_html():
    items = "".join(f'<a href="{e(l["url"])}">{e(l["name"])}</a>' for l in SITE["links"])
    return f'<nav class="social">{items}</nav>'


# ---------- images ----------

def clean_copy(src, dest, max_px=MAX_IMG):
    """Re-save an image with metadata stripped and size capped."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im.thumbnail((max_px, max_px))
        fmt = (im.format or src.suffix.lstrip(".")).upper().replace("JPG", "JPEG")
        clean = im.copy()
        clean.info = {}  # drops EXIF/GPS/XMP; Pillow only writes metadata it's handed
        if fmt == "JPEG" and clean.mode not in ("RGB", "L"):
            clean = clean.convert("RGB")
        clean.save(dest, format=fmt, quality=85)


def static_asset(key, max_px):
    """Clean a brand image from static/ into the site. Returns its URL or ''."""
    name = SITE.get(key)
    src = ROOT / "static" / name if name else None
    if not src or not src.exists():
        return ""
    clean_copy(src, OUT / "static" / name, max_px)
    return f"/static/{name}"


def publish_image(log):
    """Copy the Log image with metadata stripped and size capped. Returns its public URL."""
    name = log.get("image")
    if not name:
        return ""
    src = log["dir"] / name
    if not src.exists():
        print(f"  ! {log['id']}: image {name} not found", file=sys.stderr)
        return ""
    clean_copy(src, OUT / "logs" / log["id"] / src.name)
    return f"/logs/{log['id']}/{src.name}"


# ---------- pages ----------

def log_page(log, prev, nxt):
    img = publish_image(log)
    parts = [f'<article class="log">', f'<p class="kicker">{e(log.get("phase"))}'
             + (f' · {e(log["series"])}' if log.get("series") else "") + "</p>",
             f"<h1>{e(label(log))}</h1>"]
    parts.append(f'<div class="log-text">{text_to_html(log["body"])}</div>')
    if img:
        parts.append(f'<img class="log-image" src="{img}" alt="{e(log.get("alt") or label(log))}">')
    if log.get("credit", {}).get("text"):
        c = log["credit"]
        inner = f'<a href="{e(c["url"])}">{e(c["text"])}</a>' if c.get("url") else e(c["text"])
        parts.append(f'<p class="credit">Image: {inner}</p>')
    if log["date"]:
        parts.append(f'<p class="date">{fmt_date(log["date"])}</p>')
    if log["supplemental"]:
        s = log["supplemental"]
        parts.append(f'<section class="supplemental"><h2>Supplemental</h2>{text_to_html(s["body"])}</section>')
    social = {k: v for k, v in (log.get("social") or {}).items() if v}
    if social:
        names = {"x": "X", "threads": "Threads", "instagram": "Instagram", "facebook": "Facebook"}
        links = " · ".join(f'<a href="{e(v)}">{names.get(k, k.title())}</a>' for k, v in social.items())
        parts.append(f'<p class="discuss">Discuss on {links}</p>')
    nav = ['<nav class="prevnext">']
    nav.append(f'<a class="prev" href="{url(prev)}">← {e(label(prev))}</a>' if prev else "<span></span>")
    nav.append(f'<a class="next" href="{url(nxt)}">{e(label(nxt))} →</a>' if nxt else "<span></span>")
    nav.append("</nav>")
    parts.append("".join(nav))
    parts.append('<p class="back"><a href="/logs/">All Logs</a></p></article>')
    page(f"logs/{log['id']}/index.html", label(log), "\n".join(parts),
         description=excerpt(log["body"]), image=img, canonical=url(log))


def archive_page(logs):
    parts = ['<h1>The Logs</h1>']
    phase = None
    for log in logs:
        if log.get("phase") != phase:
            if phase is not None:
                parts.append("</ol>")
            phase = log.get("phase")
            sub = (SITE.get("phases") or {}).get(phase) or ""
            parts.append(f'<h2 class="phase">{e(phase)}</h2>'
                         + (f'<p class="phase-sub">{e(sub)}</p>' if sub else "")
                         + '<ol class="archive">')
        cls = ' class="special"' if log.get("type") == "special" else ""
        parts.append(f'<li{cls}><a href="{url(log)}">{e(label(log))}</a></li>')
    parts.append("</ol>")
    page("logs/index.html", "The Logs", "\n".join(parts),
         description=f"Every Log, in order. {TAGLINE}", canonical="/logs/")


def home_page(logs):
    latest = logs[-1]
    door = next((l for l in logs if l["id"] == "SL001"), None)
    img = f"/logs/{latest['id']}/{latest['image']}" if latest.get("image") else ""
    bg = f' style="background-image: url({BACKGROUND})"' if BACKGROUND else ""
    avatar = f'<img class="avatar" src="{ICON}" alt="">' if ICON else ""
    tagline = "<br>".join(e(l) for l in TAGLINE_LINES)
    parts = [f'<header class="hero{" has-bg" if BACKGROUND else ""}"{bg}>{avatar}'
             f'<h1>{e(SITE["title"])}</h1><p class="tagline">{tagline}</p></header>',
             '<section class="latest"><p class="kicker">Latest</p>',
             f'<h2><a href="{url(latest)}">{e(label(latest))}</a></h2>']
    parts.append(f'<div class="log-text">{text_to_html(latest["body"])}</div>')
    if img:
        parts.append(f'<a href="{url(latest)}"><img class="log-image" src="{img}" alt="{e(latest.get("alt"))}"></a>')
    parts.append('</section>')
    parts.append('<p class="cta"><a class="button" href="/logs/">All Logs</a></p>')
    if door:
        parts.append(f'<section class="door"><p class="kicker">{e(label(door))}</p>{text_to_html(door["body"])}</section>')
    page("index.html", SITE["title"], "\n".join(parts), image=img, canonical="/")


# ---------- main ----------

ICON = BACKGROUND = ICON_LINK = BRAND_ICON = ""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    (OUT / ".nojekyll").write_text("")
    global ICON, BACKGROUND, ICON_LINK, BRAND_ICON
    ICON = static_asset("icon", 512)
    BACKGROUND = static_asset("background", 1600)
    ICON_LINK = f'<link rel="icon" href="{ICON}">' if ICON else ""
    BRAND_ICON = f'<img src="{ICON}" alt="">' if ICON else ""
    logs = load_logs()
    for i, log in enumerate(logs):
        log_page(log, logs[i - 1] if i else None, logs[i + 1] if i + 1 < len(logs) else None)
    archive_page(logs)
    home_page(logs)
    page("404.html", "Not found", '<h1>Not found</h1><p><a href="/logs/">All Logs</a></p>')
    print(f"Built {len(logs)} Logs into {OUT.relative_to(ROOT)}/ (latest: {label(logs[-1])})"
          + (" [PREVIEW]" if PREVIEW else ""))


if __name__ == "__main__":
    main()
