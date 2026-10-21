from myoverl_mcp.errors import SourceProtectedError, ValidationError
from myoverl_mcp.ids import new_id
from myoverl_mcp.models import Entry
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore
from myoverl_mcp.tools import copy_resume, get_resume, remove_entry, set_layout
import pytest


def test_cannot_remove_job_from_source():
    store = ResumeStore()
    src = seed_bright(store)
    job_id = next(s for s in src.sections if s.kind == "experience").entries[0].entry_id
    with pytest.raises(SourceProtectedError):
        remove_entry(store, src.resume_id, src.revision, "req-rm", job_id)


def test_remove_job_on_copy():
    store = ResumeStore()
    src = seed_bright(store)
    copy = copy_resume(store, src.resume_id, src.revision, "req-c2", "C")
    job_id = next(s for s in copy.sections if s.kind == "experience").entries[0].entry_id
    out = remove_entry(store, copy.resume_id, copy.revision, "req-rm2", job_id)
    jobs = next(s for s in out.sections if s.kind == "experience")
    assert job_id not in [e.entry_id for e in jobs.entries]


def test_set_layout_keeps_margins_equal():
    store = ResumeStore()
    src = seed_bright(store)
    out = set_layout(store, src.resume_id, src.revision, "req-lay", top_in=0.12, bottom_in=None, side_in=0.4, project_header_lines=1, hide_section_ids=None)
    assert out.page.top_in == out.page.bottom_in == 0.12
    assert out.page.side_in == 0.4


def test_cannot_remove_project_from_source():
    store = ResumeStore()
    src = seed_bright(store)
    project_id = next(s for s in src.sections if s.kind == "projects").entries[0].entry_id
    with pytest.raises(SourceProtectedError):
        remove_entry(store, src.resume_id, src.revision, "req-rm-proj", project_id)
    assert get_resume(store, src.resume_id).revision == src.revision


def test_cannot_remove_last_education():
    store = ResumeStore()
    src = seed_bright(store)
    edu_id = next(s for s in src.sections if s.kind == "education").entries[0].entry_id
    with pytest.raises(ValidationError):
        remove_entry(store, src.resume_id, src.revision, "req-edu", edu_id)
    copy = copy_resume(store, src.resume_id, src.revision, "req-c-edu", "C")
    copy_edu = next(s for s in copy.sections if s.kind == "education").entries[0].entry_id
    with pytest.raises(ValidationError):
        remove_entry(store, copy.resume_id, copy.revision, "req-edu2", copy_edu)
    assert get_resume(store, src.resume_id).revision == src.revision
    assert get_resume(store, copy.resume_id).revision == copy.revision


def test_remove_education_when_another_remains():
    store = ResumeStore()
    src = seed_bright(store)
    copy = copy_resume(store, src.resume_id, src.revision, "req-c-edu2", "C")
    edu = next(s for s in copy.sections if s.kind == "education")
    first_id = edu.entries[0].entry_id
    extra = Entry(
        entry_id=new_id("ent"),
        kind="education",
        title="Certificate",
        fields={"school": "Other"},
    )
    edu.entries.append(extra)
    store.put(copy)
    copy = get_resume(store, copy.resume_id)
    out = remove_entry(store, copy.resume_id, copy.revision, "req-rm-edu", first_id)
    got = next(s for s in out.sections if s.kind == "education")
    ids = [e.entry_id for e in got.entries]
    assert first_id not in ids
    assert extra.entry_id in ids


def test_remove_unknown_entry_raises():
    store = ResumeStore()
    src = seed_bright(store)
    with pytest.raises(ValidationError):
        remove_entry(store, src.resume_id, src.revision, "req-miss", "ent_missing")
    assert get_resume(store, src.resume_id).revision == src.revision


def test_remove_is_idempotent_for_same_request_id():
    store = ResumeStore()
    src = seed_bright(store)
    copy = copy_resume(store, src.resume_id, src.revision, "req-c-idemp", "C")
    job_id = next(s for s in copy.sections if s.kind == "experience").entries[0].entry_id
    first = remove_entry(store, copy.resume_id, copy.revision, "req-rm-idemp", job_id)
    second = remove_entry(store, copy.resume_id, copy.revision, "req-rm-idemp", job_id)
    jobs = next(s for s in get_resume(store, copy.resume_id).sections if s.kind == "experience")
    assert first.revision == second.revision == copy.revision + 1
    assert job_id not in [e.entry_id for e in jobs.entries]
    assert len(jobs.entries) == 2
    source_jobs = next(s for s in get_resume(store, src.resume_id).sections if s.kind == "experience")
    assert job_id in [e.entry_id for e in source_jobs.entries]


def test_cannot_hide_sections_on_source():
    store = ResumeStore()
    src = seed_bright(store)
    extra_id = next(s for s in src.sections if s.kind == "extracurriculars").section_id
    with pytest.raises(SourceProtectedError):
        set_layout(
            store,
            src.resume_id,
            src.revision,
            "req-hide-src",
            top_in=None,
            bottom_in=None,
            side_in=None,
            project_header_lines=None,
            hide_section_ids=[extra_id],
        )
    assert extra_id in [s.section_id for s in get_resume(store, src.resume_id).sections]


def test_hide_section_ids_on_copy():
    store = ResumeStore()
    src = seed_bright(store)
    copy = copy_resume(store, src.resume_id, src.revision, "req-c-hide", "C")
    extra = next(s for s in copy.sections if s.kind == "extracurriculars")
    out = set_layout(
        store,
        copy.resume_id,
        copy.revision,
        "req-hide",
        top_in=None,
        bottom_in=None,
        side_in=None,
        project_header_lines=None,
        hide_section_ids=[extra.section_id],
    )
    assert extra.section_id not in [s.section_id for s in out.sections]
    assert extra.section_id in [s.section_id for s in get_resume(store, src.resume_id).sections]


def test_project_header_lines_apply_to_all_projects():
    store = ResumeStore()
    src = seed_bright(store)
    out = set_layout(
        store,
        src.resume_id,
        src.revision,
        "req-hdr",
        top_in=None,
        bottom_in=None,
        side_in=None,
        project_header_lines=1,
        hide_section_ids=None,
    )
    projects = next(s for s in out.sections if s.kind == "projects")
    assert [e.header_lines for e in projects.entries] == [1, 1, 1]
    assert out.page.max_pages == 1


def test_set_layout_from_bottom_only_keeps_margins_equal():
    store = ResumeStore()
    src = seed_bright(store)
    out = set_layout(
        store,
        src.resume_id,
        src.revision,
        "req-bot",
        top_in=None,
        bottom_in=0.2,
        side_in=None,
        project_header_lines=None,
        hide_section_ids=None,
    )
    assert out.page.top_in == out.page.bottom_in == 0.2
    assert out.page.side_in == src.page.side_in
    assert out.page.max_pages == 1


def test_set_layout_is_idempotent_for_same_request_id():
    store = ResumeStore()
    src = seed_bright(store)
    first = set_layout(
        store,
        src.resume_id,
        src.revision,
        "req-lay-idemp",
        top_in=0.12,
        bottom_in=None,
        side_in=0.4,
        project_header_lines=2,
        hide_section_ids=None,
    )
    second = set_layout(
        store,
        src.resume_id,
        src.revision,
        "req-lay-idemp",
        top_in=0.12,
        bottom_in=None,
        side_in=0.4,
        project_header_lines=2,
        hide_section_ids=None,
    )
    assert first.revision == second.revision == src.revision + 1
    stored = get_resume(store, src.resume_id)
    assert stored.page.top_in == stored.page.bottom_in == 0.12
    assert stored.page.side_in == 0.4
    assert stored.page.max_pages == 1
