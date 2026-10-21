from myoverl_mcp.errors import ValidationError
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore
from myoverl_mcp.tools import get_resume, reorder_resume
import pytest


def test_reorder_projects():
    store = ResumeStore()
    src = seed_bright(store)
    projects = next(s for s in src.sections if s.kind == "projects")
    flipped = list(reversed([e.entry_id for e in projects.entries]))
    out = reorder_resume(
        store,
        src.resume_id,
        src.revision,
        "req-ord",
        entry_orders=[{"section_id": projects.section_id, "entry_ids": flipped}],
    )
    got = next(s for s in out.sections if s.kind == "projects")
    assert [e.entry_id for e in got.entries] == flipped


def test_reorder_sections_skills_before_projects():
    store = ResumeStore()
    src = seed_bright(store)
    ids = [s.section_id for s in src.sections]
    skills = next(s for s in src.sections if s.kind == "skills")
    projects = next(s for s in src.sections if s.kind == "projects")
    new_ids = []
    for sid, section in zip(ids, src.sections):
        new_ids.append(sid)
    # education, experience, skills, projects, extras
    kinds = {s.section_id: s.kind for s in src.sections}
    ordered = [s.section_id for s in src.sections if s.kind == "education"]
    ordered += [s.section_id for s in src.sections if s.kind == "experience"]
    ordered += [skills.section_id, projects.section_id]
    ordered += [s.section_id for s in src.sections if s.kind == "extracurriculars"]
    out = reorder_resume(store, src.resume_id, src.revision, "req-sec", section_ids=ordered)
    assert [s.kind for s in out.sections] == [
        "education",
        "experience",
        "skills",
        "projects",
        "extracurriculars",
    ]


def test_requires_at_least_one_argument():
    store = ResumeStore()
    src = seed_bright(store)
    with pytest.raises(ValidationError):
        reorder_resume(store, src.resume_id, src.revision, "req-none")
    assert get_resume(store, src.resume_id).revision == src.revision


def test_missing_extra_ids_raise_validation_error():
    store = ResumeStore()
    src = seed_bright(store)
    section_ids = [s.section_id for s in src.sections]
    projects = next(s for s in src.sections if s.kind == "projects")
    skills = next(s for s in src.sections if s.kind == "skills")
    project_ids = [e.entry_id for e in projects.entries]
    row_ids = [r.row_id for r in skills.skill_rows]
    items = list(skills.skill_rows[0].items)

    with pytest.raises(ValidationError):
        reorder_resume(
            store,
            src.resume_id,
            src.revision,
            "req-sec-extra",
            section_ids=section_ids + ["sec_missing"],
        )
    with pytest.raises(ValidationError):
        reorder_resume(
            store,
            src.resume_id,
            src.revision,
            "req-sec-missing",
            section_ids=section_ids[1:],
        )
    with pytest.raises(ValidationError):
        reorder_resume(
            store,
            src.resume_id,
            src.revision,
            "req-ent-extra",
            entry_orders=[{"section_id": projects.section_id, "entry_ids": project_ids + ["ent_missing"]}],
        )
    with pytest.raises(ValidationError):
        reorder_resume(
            store,
            src.resume_id,
            src.revision,
            "req-ent-missing",
            entry_orders=[{"section_id": projects.section_id, "entry_ids": project_ids[1:]}],
        )
    with pytest.raises(ValidationError):
        reorder_resume(
            store,
            src.resume_id,
            src.revision,
            "req-row-extra",
            skill_row_ids=row_ids + ["row_missing"],
        )
    with pytest.raises(ValidationError):
        reorder_resume(
            store,
            src.resume_id,
            src.revision,
            "req-items-extra",
            skill_items=[{"row_id": skills.skill_rows[0].row_id, "items": items + ["Nope"]}],
        )
    assert get_resume(store, src.resume_id).revision == src.revision


def test_reorder_skill_rows_and_items():
    store = ResumeStore()
    src = seed_bright(store)
    skills = next(s for s in src.sections if s.kind == "skills")
    flipped_rows = list(reversed([r.row_id for r in skills.skill_rows]))
    first = skills.skill_rows[0]
    flipped_items = list(reversed(first.items))
    out = reorder_resume(
        store,
        src.resume_id,
        src.revision,
        "req-skills",
        skill_row_ids=flipped_rows,
        skill_items=[{"row_id": first.row_id, "items": flipped_items}],
    )
    got = next(s for s in out.sections if s.kind == "skills")
    assert [r.row_id for r in got.skill_rows] == flipped_rows
    moved = next(r for r in got.skill_rows if r.row_id == first.row_id)
    assert moved.items == flipped_items


def test_malformed_reorder_patches_raise_validation_error():
    store = ResumeStore()
    src = seed_bright(store)
    with pytest.raises(ValidationError):
        reorder_resume(
            store,
            src.resume_id,
            src.revision,
            "req-bad-entry-order",
            entry_orders=[{"entry_ids": []}],
        )
    with pytest.raises(ValidationError):
        reorder_resume(
            store,
            src.resume_id,
            src.revision,
            "req-bad-skill-items",
            skill_items=[{"items": []}],
        )
    assert get_resume(store, src.resume_id).revision == src.revision
