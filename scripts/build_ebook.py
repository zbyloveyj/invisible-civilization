#!/usr/bin/env python3
"""Build a print-like A5 PDF directly from all canonical chapter QMD files."""
from __future__ import annotations
import argparse, html, os, re, tempfile
from pathlib import Path
from io import BytesIO
from urllib.request import Request, urlopen
from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
    PageBreak, Spacer, HRFlowable, Image, KeepTogether)
from reportlab.platypus.tableofcontents import TableOfContents
from PIL import Image as PillowImage

NAMES=["未知的生命","疾病与城市","医学与战争","生命的密码","人体的另一半","生命的新边界"]
NUM=["一","二","三","四","五","六"]
EN=["THE UNSEEN","DISEASE AND CITY","MEDICINE AND WAR","CODE OF LIFE","WITHIN US","NEW FRONTIERS"]
C=lambda x:colors.HexColor(x)
INK,FADE,ACCENT,PAPER,LINE=C("#2E3833"),C("#6C726C"),C("#657B6D"),C("#FBF8F1"),C("#DBDBD2")

def plain(s):
    s=re.sub(r"<[^>]+>","",s)
    s=re.sub(r"\*\*(.*?)\*\*",r"\1",s)
    s=re.sub(r"\*([^*]+)\*",r"\1",s)
    s=re.sub(r"\[([^\]]+)\]\([^)]+\)",r"\1",s)
    s=re.sub(r"^#+\s*","",s.strip())
    return html.unescape(s).strip()

def safe(s):
    return html.escape(plain(s),quote=False).replace("\n","<br/>")

def styles(font):
    return {
        "body":ParagraphStyle("body",fontName=font,fontSize=10.6,leading=19.8,
             firstLineIndent=21.2,spaceAfter=5.6,wordWrap="CJK",
             alignment=TA_JUSTIFY,textColor=INK,splitLongWords=1),
        "head":ParagraphStyle("head",fontName=font,fontSize=22,leading=34,textColor=INK,spaceAfter=13),
        "volume":ParagraphStyle("volume",fontName=font,fontSize=30,leading=43,textColor=INK),
        "small":ParagraphStyle("small",fontName=font,fontSize=8.7,leading=17,textColor=FADE,spaceAfter=10,wordWrap="CJK"),
        "sub":ParagraphStyle("sub",fontName=font,fontSize=10,leading=18,textColor=ACCENT,spaceAfter=12),
        "note":ParagraphStyle("note",fontName=font,fontSize=8.7,leading=15.8,textColor=FADE,
              spaceAfter=8,wordWrap="CJK",alignment=TA_JUSTIFY),
        "ref":ParagraphStyle("ref",fontName=font,fontSize=8.0,leading=14.2,textColor=INK,
             spaceAfter=8,wordWrap="CJK"),
        "toc":ParagraphStyle("toc",fontName=font,fontSize=21,leading=34,textColor=INK,spaceAfter=15),
    }

class Heading(Paragraph):
    def __init__(self,txt,sty,label,level,key):
        super().__init__(txt,sty)
        self.toc_title,self.toc_level,self.toc_key=label,level,key

class Book(BaseDocTemplate):
    def __init__(self,path,**kw):
        BaseDocTemplate.__init__(self,path,pagesize=A5,**kw)
        l=18*mm;b=19*mm;t=19*mm
        self.addPageTemplates(PageTemplate(id="pages",frames=[Frame(l,b,A5[0]-2*l,A5[1]-t-b,
              leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=self.draw))
    def draw(self,canvas,doc):
        canvas.saveState()
        canvas.setFillColor(PAPER);canvas.rect(0,0,A5[0],A5[1],fill=1,stroke=0)
        if doc.page>1:
            canvas.setStrokeColor(LINE);canvas.line(18*mm,A5[1]-13.2*mm,A5[0]-18*mm,A5[1]-13.2*mm)
            canvas.setFillColor(FADE);canvas.setFont("Ming",7.2)
            canvas.drawString(18*mm,A5[1]-11.2*mm,"看不见的文明 · 微生物与人类的三百年")
            canvas.drawCentredString(A5[0]/2,11.7*mm,str(doc.page))
        canvas.restoreState()
    def afterFlowable(self,f):
        if isinstance(f,Heading):
            self.canv.bookmarkPage(f.toc_key)
            self.canv.addOutlineEntry(f.toc_title,f.toc_key,level=f.toc_level,closed=False)
            self.notify("TOCEntry",(f.toc_level,f.toc_title,self.page,f.toc_key))

def read_one(path):
    text=path.read_text(encoding="utf-8")
    title=re.search(r"^#\s+([^\n]+?)\s*\{\.unnumbered\}",text,re.M)
    main=re.search(r"::: \{\.novel-chapter\}\s*\n(.*?)\n\s*:::",text,re.S)
    hist=re.search(r"::: \{\.history-note\}\s*\n(.*?)\n\s*:::",text,re.S)
    date=re.search(r'<p class="chapter-dateline">([^<]+)</p>',text)
    if not (title and main and hist):
        raise ValueError("Incomplete chapter "+str(path))
    return plain(title.group(1)),plain(date.group(1)) if date else "",\
        [x.strip() for x in re.split(r"\n\s*\n",main.group(1).strip()) if x.strip()],\
        [x.strip() for x in re.split(r"\n\s*\n",hist.group(1).strip()) if x.strip()]

def illustration(piece,sty,root,temp):
    m=re.search(r'<img[^>]*src="([^"]+)"',piece)
    if not m:return []
    src=html.unescape(m.group(1))
    cap=re.search(r"<figcaption>(.*?)</figcaption>",piece,re.S)
    caption=plain(cap.group(1)) if cap else "科学图版"
    file=None
    if src.startswith("https://"):
        try:
            import hashlib
            file=temp/(hashlib.sha256(src.encode()).hexdigest()[:20]+".png")
            if not file.exists():
                req=Request(src,headers={"User-Agent":"BookEdition/1.0 scientific-novel"})
                with urlopen(req,timeout=6) as resp:
                    PillowImage.open(BytesIO(resp.read(10000000))).convert("RGB").save(file)
        except Exception as e:
            print("Illustration unavailable:",str(e)[:110],flush=True)
            file=None
    else:
        local=(root/"chapters"/"volume-01"/src).resolve() if src.startswith("../../") else (root/src).resolve()
        if local.exists():
            if local.suffix==".svg":
                try:
                    import cairosvg
                    file=temp/(local.stem+".png")
                    if not file.exists():cairosvg.svg2png(url=str(local),write_to=str(file),output_width=1350)
                except Exception as e:print("SVG unavailable:",str(e)[:110],flush=True)
            else:file=local
    pieces=[Spacer(1,4.5*mm)]
    if file and Path(file).is_file():
        try:
            with PillowImage.open(file) as im:w,h=im.size
            ratio=min((A5[0]-36*mm)/w,85*mm/h)
            pieces.extend([Image(str(file),width=w*ratio,height=h*ratio),Spacer(1,2.4*mm)])
        except Exception as e:print("Image invalid:",str(e)[:100],flush=True)
    else:caption="【该图像请查看在线阅读版】"+caption
    pieces.extend([Paragraph(safe(caption),sty["small"]),Spacer(1,3*mm)])
    return [KeepTogether(pieces)]

def build(root,destination):
    font_path=next((p for p in ["/usr/share/fonts/truetype/arphic/uming.ttc",
         "/usr/share/fonts/truetype/baekmuk/batang.ttf"] if os.path.isfile(p)),None)
    if not font_path:raise RuntimeError("Missing CJK TrueType font: install fonts-arphic-uming")
    pdfmetrics.registerFont(TTFont("Ming",font_path))
    st=styles("Ming")
    chapters=[]
    for n in range(1,49):
        p=root/f"chapters/volume-{(n-1)//8+1:02d}/chapter-{n:02d}.qmd"
        chapters.append(read_one(p))
    print("PDF INPUT: 48 chapters, manuscript latest",flush=True)
    flow=[Spacer(1,49*mm),Paragraph("一心问道　著",st["sub"]),Spacer(1,16*mm),
          Paragraph("看不见的文明",ParagraphStyle("cover",parent=st["volume"],fontSize=34,leading=49)),
          Spacer(1,4*mm),Paragraph("微生物与人类的三百年",st["sub"]),
          Spacer(1,27*mm),HRFlowable(width="50%",color=ACCENT,thickness=1,hAlign="LEFT"),
          Spacer(1,8*mm),Paragraph("六卷 · 四十八章<br/>科学历史长篇小说",st["small"]),PageBreak()]
    flow.append(Heading("关于本书",st["toc"],"关于本书",0,"about"))
    preface=[
      "本书以17世纪以来的微生物学与医学史为背景，通过历史和现代人物的故事，讲述人类如何逐渐认识肉眼难见的生命，以及新的知识怎样进入真实生活。",
      "这是根据GitHub仓库现行48章正文编排的公开文学修订稿。书中普通人物及其生活经历为文学虚构；每章末附真实历史与科学解读，部分史料仍需出版前终审。",
      "PDF由正文自动生成，包含六卷目录、章节书签、页码与参考资料。历史图片如因外部馆藏连接不可用而无法嵌入，相关文字说明仍会保留。",
      "作者：一心问道。公开阅读不等于放弃版权。未经许可不得将全书用于再出版、改编或商业使用。",
    ]
    for x in preface:flow.append(Paragraph(safe(x),st["body"]))
    flow.extend([PageBreak(),Paragraph("六卷目录",st["toc"])])
    toc=TableOfContents()
    toc.levelStyles=[
       ParagraphStyle("t0",fontName="Ming",fontSize=11,leading=23,textColor=ACCENT,spaceBefore=9),
       ParagraphStyle("t1",fontName="Ming",fontSize=9.0,leading=18,leftIndent=13,rightIndent=17,textColor=INK)]
    flow.append(toc);flow.append(PageBreak())
    with tempfile.TemporaryDirectory() as td:
        cache=Path(td)
        for v,name in enumerate(NAMES):
            flow.append(Heading("第"+NUM[v]+"卷",st["sub"],"第"+NUM[v]+"卷 · "+name,0,"volume"+str(v+1)))
            flow.extend([Spacer(1,22*mm),Paragraph(EN[v],st["sub"]),
               Spacer(1,10*mm),Paragraph(name,st["volume"]),Spacer(1,15*mm),
               HRFlowable(width="35%",thickness=1.2,color=ACCENT,hAlign="LEFT"),
               Spacer(1,11*mm),Paragraph("八章故事 · 真实历史与科学解读",st["small"]),PageBreak()])
            for i in range(v*8,v*8+8):
                title,date,body,notes=chapters[i]
                flow.append(Paragraph("第"+NUM[v]+"卷　·　"+name,st["sub"]))
                flow.append(Heading(safe(title),st["head"],title,1,"chapter"+str(i+1)))
                flow.append(Paragraph(safe(date),st["small"]))
                flow.append(HRFlowable(width="100%",thickness=.5,color=LINE,spaceAfter=6*mm))
                for paragraph in body:
                    if paragraph.startswith("<figure"):
                        flow.extend(illustration(paragraph,st,root,cache))
                    else:
                        flow.append(Paragraph(safe(paragraph),st["body"]))
                flow.extend([Spacer(1,8*mm),HRFlowable(width="100%",thickness=.8,color=LINE,spaceAfter=5*mm),
                   Paragraph("真实历史与科学解读",st["sub"])])
                for note in notes:
                    if note.startswith("##"):continue
                    flow.append(Paragraph(safe(note),st["note"]))
                flow.append(PageBreak())
        refs=root/"appendices/references.qmd"
        if refs.exists():
            flow.append(Heading("史料与科学参考",st["toc"],"史料与科学参考",0,"references"))
            flow.append(Paragraph("保留57个书目编号；部分历史出版物的版次与引用信息仍在终审。",st["small"]))
            for ref in re.split(r"\n\s*\n",refs.read_text(encoding="utf-8")):
                if re.match(r"^\[\d{2}\]",ref.strip()):
                    flow.append(Paragraph(safe(ref),st["ref"]))
        destination.parent.mkdir(parents=True,exist_ok=True)
        doc=Book(str(destination),pageCompression=1,invariant=1,
            title="看不见的文明：微生物与人类的三百年",author="一心问道")
        doc.multiBuild(flow,maxPasses=4)
    print("PDF WRITTEN:",destination,destination.stat().st_size,"bytes",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=".")
    ap.add_argument("--output",default="downloads/invisible-civilization-complete.pdf")
    args=ap.parse_args()
    root=Path(args.root).resolve()
    output=Path(args.output)
    if not output.is_absolute():output=root/output
    build(root,output)
