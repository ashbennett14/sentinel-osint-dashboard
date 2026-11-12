from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.brief_pdf import article_ids, render_brief
from app.database import Base, get_db
from app.main import app
from app.models import Article, Brief


CONTENT = """# ANALYST BRIEF
**Classification:** obsolete label
**Period covered:** 2026-11-10 06:00Z to 2026-11-12 06:00Z

## 1. EXECUTIVE SUMMARY
An example development [[article:7], [article:8]].

## 2. KEY DEVELOPMENTS
- **First item:** [Publisher](https://example.org/published).
  - A supporting indicator.
- An ordered source reference [article:7].
"""


def test_brief_pdf_includes_safe_links_and_a4_layout():
    brief = Brief(id=13, ao="AO_BALKANS", content=CONTENT, generated_at=datetime(2026, 11, 12, 6))
    pdf, name = render_brief(brief, {7: ("Example article", "https://example.org/linked"),
                                     8: ("Unsafe link", "javascript:alert(1)")})
    assert article_ids(CONTENT) == [7, 8]
    assert pdf.startswith(b"%PDF-")
    assert name == "sentinel-balkans-analyst-brief-2026-11-12-13.pdf"
    assert b"/MediaBox [ 0 0 595." in pdf
    assert b"https://example.org/linked" in pdf
    assert b"https://example.org/published" in pdf
    assert b"javascript:" not in pdf


def test_pdf_endpoint_supports_viewing_downloading_and_missing_briefs():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Brief(id=13, ao="AO_BALKANS", content=CONTENT, generated_at=datetime(2026, 11, 12, 6)))
        db.add(Article(id=7, ao="AO_BALKANS", title="Example article", url="https://example.org/linked",
                       published_at=datetime(2026, 11, 12, 6)))
        db.add(Article(id=8, ao="AO_LEVANT", title="Other region", url="https://example.org/other",
                       published_at=datetime(2026, 11, 12, 6)))
        db.commit()

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    try:
        client = TestClient(app)
        inline = client.get("/api/briefs/13/pdf")
        download = client.get("/api/briefs/13/pdf?download=true")
        for response, disposition in ((inline, "inline"), (download, "attachment")):
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert response.headers["content-disposition"].startswith(disposition)
            assert b"https://example.org/linked" in response.content
            assert b"https://example.org/other" not in response.content
        assert client.get("/api/briefs/999/pdf").status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
