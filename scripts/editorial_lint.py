#!/usr/bin/env python3
"""Editorial integrity checks for the six-volume Chinese literary manuscript."""
from pathlib import Path
import re
from difflib import SequenceMatcher

chapters=[]
for n in range(1,49):
    p=Path(f"chapters/volume-{(n-1)//8+1:02d}/chapter-{n:02d}.qmd")
    if not p.is_file():raise SystemExit(f"Missing chapter file {p}")
    txt=p.read_text(encoding="utf-8")
    if not re.search(r"^# 第.{1,7}章[ \u3000]",txt,re.M):raise SystemExit(f"Missing chapter heading: {p}")
    m=re.search(r"::: \{\.novel-chapter\}\s*\n(.*?)\n\n:::",txt,re.S)
    if not m:raise SystemExit(f"Missing novel chapter block: {p}")
    if "真实历史与科学解读" not in txt:raise SystemExit(f"Missing fact-fiction explanation: {p}")
    prose=re.sub(r"<figure\b.*?</figure>","",m.group(1),flags=re.S)
    paras=[x.strip() for x in prose.split("\n\n") if x.strip()]
    if len(paras)<8:raise SystemExit(f"Unexpectedly short chapter structure: {p} ({len(paras)} paragraphs)")
    if any(len(s)<55 for s in paras):
        raise SystemExit(f"Very short narrative paragraph in {p}")
    for a,b in zip(paras,paras[1:]):
        if SequenceMatcher(None,a,b).ratio()>.96:
            raise SystemExit(f"Nearly duplicated adjacent paragraphs in {p}")
    chapters.append((n,len(prose),txt,paras))
for n in [35,37,38,40,41,43,44,47]:
    if chapters[n-1][1]<3750:raise SystemExit(f"Expanded chapter unexpectedly short: {n}")
if "有一位参与研究的老人" in chapters[34][2]:raise SystemExit("Chapter 35: unsupported elderly HMP participant")
ch38=chapters[37][2]
if ch38.find("离开树林时")>ch38.find("回城的车上"):raise SystemExit("Chapter 38 forest/car chronology reverted")
ch43=chapters[42][2]
if ch43.find("展板试读结束后")<ch43.find("第二天，叶岚请团队成员参加一次展板试读"):raise SystemExit("Chapter 43 trial ordering reverted")

# Keep the bibliography's 57-item identifiers and per-item source traceability intact.
references=Path("appendices/references.qmd").read_text(encoding="utf-8")
entries=[(int(line[1:3]),line[4:].strip()) for line in references.splitlines() if len(line)>4 and line.startswith('[') and line[1:3].isdigit() and line[3]==']']
if [n for n,_ in entries]!=list(range(1,58)):
    raise SystemExit("Bibliography must preserve numbered items 01–57")
if any(not re.search(r"https?://",line) for _,line in entries):
    raise SystemExit("Every bibliography item must contain a DOI or traceable institutional/archive URL")
if not Path("appendices/reference-audit.qmd").exists():
    raise SystemExit("Bibliography audit file missing")
print("PASS: 57 numbered reference records with source links")
print("PASS: 48 chapter source files, fact notes, long-form paragraphs, and priority continuity checks.")
