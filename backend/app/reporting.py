"""Presentation helpers for original source text and publisher attribution."""
import html
import re
from urllib.parse import urlsplit

_NON_LATIN = re.compile(r"[\u0370-\u052f\u0590-\u08ff\u0900-\u0dff\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def clean_text(value):
    text = value or ""
    for _ in range(2):
        text = html.unescape(re.sub(r"<[^>]*>", " ", text))
    return " ".join(text.split())


def publisher_name(article):
    """Use the publisher suffix carried by Google News, not the monitor label."""
    source = getattr(article, "source", None)
    source_name = getattr(source, "name", None)
    try:
        host = urlsplit(getattr(article, "url", "") or "").hostname
    except ValueError:
        return source_name
    if host == "news.google.com":
        _, separator, publisher = clean_text(getattr(article, "title", "")).rpartition(" - ")
        if separator and publisher and len(publisher) <= 100:
            return publisher
        return "Google News (publisher not identified)"
    return source_name


def may_need_translation(title, summary):
    for value in (title, summary):
        text = clean_text(value)
        letters = sum(ch.isalpha() for ch in text)
        if letters and len(_NON_LATIN.findall(text)) / letters >= 0.3:
            return True
    return False
