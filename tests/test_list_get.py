from myoverl_mcp.errors import NotFoundError
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore
from myoverl_mcp.tools import get_resume, list_resumes
import pytest


def test_list_includes_bright_source():
    store = ResumeStore()
    seed_bright(store)
    rows = list_resumes(store)
    assert [r.name for r in rows] == ["Bright"]
    assert rows[0].role == "source"


def test_get_returns_sections_and_heading():
    store = ResumeStore()
    seeded = seed_bright(store)
    got = get_resume(store, seeded.resume_id)
    kinds = [s.kind for s in got.sections]
    assert kinds == ["education", "experience", "projects", "skills", "extracurriculars"]
    assert got.heading.slots[0].kind == "phone"
    assert got.heading.slots[1].kind == "email"


def test_get_missing():
    store = ResumeStore()
    with pytest.raises(NotFoundError):
        get_resume(store, "nope")
