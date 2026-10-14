#!/usr/bin/env python3
"""Check the published chapter set, internal links, and inline reader JavaScript."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import re, subprocess, sys

root=Path("_site").resolve()
need=["index.html","contents.html","timeline.html","about.html","download.html","figures.html"]
need += [f"volumes/volume-{v:02d}.html" for v in range(1,7)]
need += [f"chapters/volume-{(n-1)//8+1:02d}/chapter-{n:02d}.html" for n in range(1,49)]
missing=[p for p in need if not (root/p).is_file()]
if missing: raise SystemExit("Missing pages: "+", ".join(missing))
class Parser(HTMLParser):
 def __init__(self): super().__init__();self.hrefs=[]
 def handle_starttag(self,tag,attrs):
  if tag=="a":
   value=dict(attrs).get("href")
   if value:self.hrefs.append(value)
bad=[];checked=0
for p in root.rglob("*.html"):
 parser=Parser();parser.feed(p.read_text(encoding="utf-8"))
 for href in parser.hrefs:
  u=urlsplit(href)
  if u.scheme or u.netloc or not u.path.lower().endswith(".html"):continue
  link=unquote(u.path)
  if link.startswith("/invisible-civilization/"):target=root/link.removeprefix("/invisible-civilization/")
  elif link.startswith("/"):continue
  else:target=p.parent/link
  checked+=1
  if not target.is_file():bad.append((str(p.relative_to(root)),href))
if bad:
 for f,h in bad[:30]:print("BROKEN:",f,"->",h,file=sys.stderr)
 raise SystemExit(f"{len(bad)} broken HTML links")
reader=Path("styles/reader.html").read_text(encoding="utf-8")
blocks=re.findall(r"<script[^>]*>(.*?)</script>",reader,flags=re.S)
if not blocks:raise SystemExit("Missing inline reader scripts")
temp=Path("_site/_reader_syntax_check.js")
try:
 temp.write_text("\n;\n".join(blocks),encoding="utf-8")
 subprocess.run(["node","--check",str(temp)],check=True)
finally:temp.unlink(missing_ok=True)

# Editorial illustration QA: verify source-controlled SVG plates, alt texts and in-story placement.
from xml.etree import ElementTree
for plate in Path("assets/plates").glob("*.svg"):
    ElementTree.parse(plate)
figure_count = 0
chapters_with_figures = []
for num in range(1,49):
    path = root / f"chapters/volume-{(num-1)//8+1:02d}/chapter-{num:02d}.html"
    html = path.read_text(encoding="utf-8")
    blocks = re.findall(r'<figure\b[^>]*book-plate[^>]*>[\s\S]*?</figure>', html)
    if blocks:
        chapters_with_figures.append(num)
    for block in blocks:
        figure_count += 1
        if not re.search(r'<figcaption\b', block) or not re.search(r'<img\b[^>]*\balt="[^"]+"', block):
            raise SystemExit(f"Figure missing caption or accessible alt: chapter {num}")
        m = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', block)
        if not m:
            raise SystemExit(f"Figure missing image source: chapter {num}")
        src = m.group(1)
        if not src.startswith(("http://","https://")):
            target = (path.parent / src).resolve()
            if not target.is_file():
                raise SystemExit(f"Missing local image: {target} (chapter {num})")
if figure_count < 12:
    raise SystemExit(f"Expected at least 12 in-story plates; found {figure_count}")
# The plate atlas and the narrative should expose the same count of referenced items.
fig_html=(root/"figures.html").read_text(encoding="utf-8")
indexed_ids=set(re.findall(r'data-plate-id="(plate-[^"]+)"',fig_html))
indexed=len(indexed_ids)
if indexed!=figure_count:
    raise SystemExit(f"Figure atlas count {indexed} does not match narrative {figure_count}")
if not (root/"assets/plates/hgt-mechanisms.svg").is_file():
    raise SystemExit("Missing HGT plate asset")
print(f"PASS: {figure_count} illustrated figures in chapters {chapters_with_figures}; atlas {indexed} plates")


# Regression guard: a stray Markdown paragraph after the final volume card must never
# become the seventh CSS-grid cell on the homepage.
class VolumeGridParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_grid = False
        self.depth = 0
        self.direct_children = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self.in_grid:
            if tag == "div" and "ic-volume-grid" in attrs.get("class","").split():
                self.in_grid = True
                self.depth = 1
            return
        if self.depth == 1:
            self.direct_children.append((tag, attrs.get("class", ""), attrs.get("href","")))
        if tag not in {"br","img","input","hr","meta","link","source","wbr","area"}:
            self.depth += 1
    def handle_endtag(self, tag):
        if not self.in_grid:
            return
        if tag not in {"br","img","input","hr","meta","link","source","wbr","area"}:
            self.depth -= 1
            if self.depth == 0:
                self.in_grid = False

homepage = (root / "index.html").read_text(encoding="utf-8")
grid_parser = VolumeGridParser()
grid_parser.feed(homepage)
if len(grid_parser.direct_children) != 6 or any(
    tag != "a" or "ic-volume" not in classes.split() or not href
    for tag, classes, href in grid_parser.direct_children
):
    raise SystemExit(
        "Homepage volume grid must contain exactly six linked cards, no blank cells: "
        + repr(grid_parser.direct_children)
    )
print("PASS: exactly six homepage volume cards; no empty seventh grid cell.")

print(f"PASS: {len(need)} book pages; {checked} local links; reader script syntax.")
