import base64
import shutil

import pytest
from starlette.testclient import TestClient

from myoverl_mcp.app import create_app
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore


def test_preview_snapshot_and_revision(monkeypatch):
    store = ResumeStore()
    resume = seed_bright(store)
    calls = []

    def build(snapshot):
        calls.append(snapshot)
        return b"%PDF-test", {"f0": {"kind": "heading-name", "raw": snapshot.heading.name}}

    monkeypatch.setattr("myoverl_mcp.app.compile_preview", build)
    client = TestClient(create_app(store))
    response = client.get(f"/api/resumes/{resume.resume_id}/preview?revision={resume.revision}")
    assert response.status_code == 200
    payload = response.json()
    assert base64.b64decode(payload["pdf"]) == b"%PDF-test"
    assert payload["resume_id"] == resume.resume_id
    assert payload["revision"] == resume.revision
    assert payload["fields"]["f0"]["raw"] == resume.heading.name
    assert len(calls) == 1
    assert client.get(f"/api/resumes/{resume.resume_id}/preview?revision=999").status_code == 409
    assert client.get("/api/resumes/missing/preview").status_code == 404
    assert len(calls) == 1
    assert store.get(resume.resume_id) == resume


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="pdflatex not installed")
@pytest.mark.parametrize("empty_fields", [False, True])
def test_preview_annotations_preserve_export_pixels_and_field_ids(tmp_path, empty_fields):
    pdf = pytest.importorskip("pymupdf")
    from myoverl_mcp.compile import compile_pdf, compile_preview

    resume = seed_bright(ResumeStore())
    if empty_fields:
        for section in resume.sections:
            for entry in section.entries:
                entry.title = ""
                entry.fields = {key: "" for key in entry.fields}
                entry.technologies = []
                for bullet in entry.bullets:
                    bullet.text = ""
    compiled, fields = compile_preview(resume)
    exported = compile_pdf(resume, tmp_path / "export.pdf")
    with pdf.open(stream=compiled, filetype="pdf") as preview, pdf.open(exported) as normal:
        assert len(preview) == len(normal) == 1
        for marked, clean in zip(preview, normal):
            assert marked.get_pixmap(matrix=pdf.Matrix(2, 2)).samples == clean.get_pixmap(matrix=pdf.Matrix(2, 2)).samples
            assert marked.get_text() == clean.get_text()
        marker_urls = [link["uri"] for page in preview for link in page.get_links() if link.get("uri", "").startswith("https://myoverl.invalid/edit/")]
        assert {url.rsplit("/", 1)[-1] for url in marker_urls} == set(fields)
        assert not any("myoverl.invalid" in link.get("uri", "") for page in normal for link in page.get_links())
    bullets = {b.bullet_id: b.text for s in resume.sections for e in s.entries for b in e.bullets}
    assert {field["id"]: field["raw"] for field in fields.values() if field["kind"] == "bullet"} == bullets
    assert {field["kind"] for field in fields.values()} == {"heading-name", "slot-text", "bullet", "title", "field", "honors", "coursework", "techs", "link", "skill-title", "skill-items"}
