#!/usr/bin/env python3
"""Check the published chapter set, internal links, and inline reader JavaScript."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import re, subprocess, sys

root=Path("_site").resolve()
need=["index.html","contents.html","timeline.html","about.html","download.html"]
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
print(f"PASS: {len(need)} book pages; {checked} local links; reader script syntax.")
