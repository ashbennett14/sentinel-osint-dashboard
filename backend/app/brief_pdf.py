"""Typeset the selected analyst brief as a standalone, print-ready A4 PDF."""

import re
import unicodedata
from datetime import timezone
from html import escape
from io import BytesIO
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, ListFlowable, ListItem, PageTemplate, Paragraph, Preformatted


REGIONS = {
    "AO_HIGH_NORTH": ("High North, Finland & the Baltics", "high-north"),
    "AO_EUROPE": ("Ukraine & Eastern Europe", "eastern-europe"),
    "AO_BALKANS": ("The Balkans", "balkans"),
    "AO_LEVANT": ("The Levant", "levant"),
}
ARTICLE = re.compile(r"\[article:(\d{1,18})\]", re.I)
ARTICLE_GROUP = re.compile(r"\[((?:\[article:\d{1,18}\](?:\s*,\s*)?)+)\]", re.I)
PERIOD = re.compile(r"^\s*(?:\*\*)?Period covered:(?:\*\*)?\s*(.+?)\s*$", re.I | re.M)
CLASSIFICATION = re.compile(r"^\s*(?:\*\*)?Classification:.*$", re.I | re.M)
DASHES = str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2212"})
INK = HexColor("#101d2c")
SLATE = HexColor("#33465a")
MUTED = HexColor("#52677b")
ACCENT = HexColor("#47d4f5")
TEAL = HexColor("#006781")
RULE = HexColor("#d7e2ea")
MARGIN = 49
MARKDOWN = MarkdownIt("commonmark", {"html": False})


def article_ids(content):
    return list(dict.fromkeys(int(value) for value in ARTICLE.findall(content)))[:200]


def _link(url):
    try:
        parsed = urlsplit(url or "")
        if parsed.scheme in ("https", "http") and parsed.hostname and not re.search(r'[\s<>"\\]', url):
            return url
    except ValueError:
        pass
    return ""


def _markup(value):
    return escape("".join(c for c in (value or "").translate(DASHES)
                          if unicodedata.category(c) != "So"))


def _reference_title(value):
    # Source headlines may contain decorative glyphs or scripts outside the
    # base PDF font. Keep readable Latin text and always retain the actual link.
    text = []
    for c in (value or "").translate(DASHES):
        try:
            c.encode("cp1252")
            text.append(c)
        except UnicodeEncodeError:
            text.append(unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode())
    title = " ".join("".join(text).split())
    return _markup(title if any(c.isalpha() for c in title) else "Open original article")


def _citations(content, links):
    numbers = {id: i for i, id in enumerate(article_ids(content), 1)}
    def replace(match):
        id = int(match.group(1))
        url = _link(links.get(id, ("", ""))[1])
        return f"[{numbers[id]}](<{url}>)" if url and id in numbers else f"Article {id}"
    result = ARTICLE_GROUP.sub(lambda group: "(" + ", ".join(replace(m) for m in ARTICLE.finditer(group[1])) + ")", content)
    result = ARTICLE.sub(lambda m: "(" + replace(m) + ")", result)
    return result, numbers


def _inline(node):
    tag = node.type
    if tag in ("text", "code_inline", "html_inline"):
        return _markup(node.content)
    if tag in ("softbreak", "hardbreak"):
        return " " if tag == "softbreak" else "<br/>"
    content = "".join(_inline(child) for child in node.children or ())
    if tag in ("strong", "em"):
        name = "b" if tag == "strong" else "i"
        return f"<{name}>{content}</{name}>"
    if tag == "link":
        url = _link(node.attrs.get("href"))
        if url:
            return f'<a href="{escape(url)}" color="#006781"><u>{content}</u></a>'
    return content


BODY = ParagraphStyle("Body", fontName="Times-Roman", fontSize=11.5, leading=16.2,
                      textColor=INK, spaceAfter=9, allowWidows=0, allowOrphans=0)
SECTION = ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=15, leading=19,
                         textColor=INK, spaceBefore=16, spaceAfter=6, keepWithNext=True)
SUB = ParagraphStyle("Subsection", parent=SECTION, fontSize=11.5, leading=15, spaceBefore=9)
REFERENCE = ParagraphStyle("Reference", parent=BODY, fontName="Helvetica", fontSize=9.2, leading=13)


def _heading(value):
    if value.isupper():
        value = value.title()
        for acronym in ("AO", "EU", "UN", "UK", "NATO", "OSINT", "US"):
            value = re.sub(rf"\b{acronym.title()}\b", acronym, value)
    match = re.match(r"^(\d+)[.)]\s*(.*)$", value)
    if match:
        return f'<font color="#006781" size="10">{int(match[1]):02d}</font>   {_markup(match[2])}'
    return _markup(value)


def _flowables(nodes):
    for node in nodes:
        kind = node.type
        if kind == "heading":
            if node.tag == "h1":
                continue
            inline = node.children[0]
            yield Paragraph(_heading(inline.content), SECTION if node.tag == "h2" else SUB)
        elif kind == "paragraph":
            yield Paragraph(_inline(node), BODY)
        elif kind in ("bullet_list", "ordered_list"):
            items = [ListItem(list(_flowables(item.children))) for item in node.children]
            if items:
                yield ListFlowable(items, bulletType="bullet" if kind == "bullet_list" else "1",
                                   start=node.attrs.get("start") or ("bulletchar" if kind == "bullet_list" else "1"),
                                   leftIndent=17, bulletDedent=13, bulletFontName="Helvetica",
                                   bulletFontSize=9, bulletColor=TEAL)
        elif kind in ("code_block", "fence"):
            yield Preformatted(node.content.translate(DASHES), BODY, maxLineLength=92)
        elif node.children:
            yield from _flowables(node.children)


def _compass(c, x, y, size):
    c.saveState()
    c.translate(x, y)
    c.scale(size / 64, size / 64)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(2.2)
    def path(points, fill=None):
        p = c.beginPath()
        p.moveTo(*points[0])
        for point in points[1:]:
            p.lineTo(*point)
        p.close()
        if fill:
            c.setFillColor(fill)
        c.drawPath(p, fill=int(fill is not None), stroke=int(fill is None))
    path([(32, 61), (61, 32), (32, 3), (3, 32)])
    path([(32, 54), (36, 36), (54, 32), (36, 28), (32, 10), (28, 28), (10, 32), (28, 36)], white)
    path([(32, 54), (36, 36), (32, 32), (28, 36)], ACCENT)
    c.restoreState()


def _letterspace(c, x, y, text, font, size, colour, spacing=1.4):
    c.saveState()
    c.setFillColor(colour)
    obj = c.beginText(x, y)
    obj.setFont(font, size)
    obj.setCharSpace(spacing)
    obj.textLine(text)
    c.drawText(obj)
    c.restoreState()


def render_brief(brief, links=None):
    links = links or {}
    region, slug = REGIONS.get(brief.ao, ("Regional Assessment", "regional"))
    stamp = brief.generated_at
    stamp = (stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp).astimezone(timezone.utc)
    date = stamp.strftime("%d %B %Y")
    period = PERIOD.search(brief.content)
    content = CLASSIFICATION.sub("", PERIOD.sub("", brief.content))
    content = re.sub(r"(\)\.)\.(?=\s|$)", r"\1", content)
    content, numbers = _citations(content, links)
    story = list(_flowables(SyntaxTreeNode(MARKDOWN.parse(content)).children))
    references = [(number, links[id][0], _link(links[id][1])) for id, number in numbers.items()
                  if id in links and _link(links[id][1])]
    if references:
        story.append(Paragraph("Referenced Articles", SECTION))
        for number, title, url in references:
            story.append(Paragraph(f'<b>{number:02d}</b>   <a href="{escape(url)}" color="#006781"><u>{_reference_title(title)}</u></a>', REFERENCE))
    if not story:
        story = [Paragraph("No text was available in this edition.", BODY)]

    width, height = A4
    stream = BytesIO()
    doc = BaseDocTemplate(stream, pagesize=A4, title=f"SENTINEL Daily Analyst Brief | {region} | {date}",
                          author="SENTINEL", subject=f"Open-source intelligence assessment: {region}")

    def draw_page(c, document):
        first = document.page == 1
        band = 170 if first else 67
        c.saveState()
        c.setFillColor(INK)
        c.rect(0, height-band, width, band, fill=1, stroke=0)
        c.setFillColor(ACCENT)
        c.rect(0, height-band, width, 2, fill=1, stroke=0)
        _compass(c, MARGIN, height-66 if first else height-52, 31 if first else 26)
        _letterspace(c, MARGIN+(42 if first else 35), height-(53 if first else 42), "SENTINEL",
                     "Helvetica-Bold", 15 if first else 11, white, 2.3 if first else 1.6)
        if first:
            c.setStrokeColor(HexColor("#22384b"))
            c.setLineWidth(.7)
            for radius in (28, 43, 58):
                c.circle(width-77, height-80, radius, stroke=1, fill=0)
            c.line(width-138, height-80, width-16, height-80)
            c.line(width-77, height-141, width-77, height-19)
            _letterspace(c, MARGIN, height-90, "DAILY ANALYST BRIEF", "Helvetica-Bold", 9, ACCENT)
            c.setFont("Helvetica-Bold", 27)
            c.setFillColor(white)
            c.drawString(MARGIN, height-121, region)
            _letterspace(c, MARGIN, height-146, "OPEN-SOURCE INTELLIGENCE", "Helvetica", 8, HexColor("#b4c5d0"))
            c.setFont("Helvetica-Bold", 10)
            c.drawRightString(width-MARGIN, height-146, date)
        else:
            c.setFillColor(white)
            c.setFont("Helvetica", 9)
            c.drawRightString(width-MARGIN, height-41, region + "  /  " + date)
        c.setStrokeColor(RULE)
        c.line(MARGIN, 43, width-MARGIN, 43)
        _letterspace(c, MARGIN, 28, "SENTINEL  /  DAILY ANALYST BRIEF", "Helvetica-Bold", 7, MUTED, .8)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawRightString(width-MARGIN, 28, f"PAGE {document.page:02d}")
        c.restoreState()

    if period:
        note = ParagraphStyle("Period", fontName="Helvetica", fontSize=9, leading=13,
                              textColor=SLATE, alignment=TA_LEFT, spaceAfter=10)
        story.insert(0, Paragraph("<b>REPORTING PERIOD</b> &nbsp;&nbsp; " + _markup(period[1].strip("* ")), note))
    def frame(top):
        return Frame(MARGIN, 62, width-2*MARGIN, height-top-62, leftPadding=0, rightPadding=0,
                     topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="opening", frames=frame(191), onPage=draw_page, autoNextPageTemplate="continuation"),
        PageTemplate(id="continuation", frames=frame(90), onPage=draw_page),
    ])
    doc.build(story)
    return stream.getvalue(), f"sentinel-{slug}-analyst-brief-{stamp:%Y-%m-%d}-{brief.id}.pdf"
