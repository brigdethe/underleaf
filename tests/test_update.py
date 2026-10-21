from myoverl_mcp.errors import ValidationError
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore
from myoverl_mcp.tools import copy_resume, get_resume, update_resume
import pytest


def test_update_bullet_on_copy_only_changes_copy():
    store = ResumeStore()
    src = seed_bright(store)
    copy = copy_resume(store, src.resume_id, src.revision, "req-c", "Copy")
    bullet_id = copy.sections[1].entries[2].bullets[-1].bullet_id  # Maddy Confluence
    update_resume(
        store,
        copy.resume_id,
        copy.revision,
        "req-u",
        bullets=[{"bullet_id": bullet_id, "text": "Covered 12 transaction and account-balance flows with automated end-to-end tests in Spring Boot Test."}],
    )
    assert "Covered 12" in get_resume(store, copy.resume_id).sections[1].entries[2].bullets[-1].text
    assert "Covered 12" not in get_resume(store, src.resume_id).sections[1].entries[2].bullets[-1].text


def test_heading_slots_phone_email_first():
    store = ResumeStore()
    src = seed_bright(store)
    updated = update_resume(
        store,
        src.resume_id,
        src.revision,
        "req-h",
        heading={
            "name": "Beth Example",
            "slots": [
                {"kind": "linkedin", "href": "https://www.linkedin.com/in/beth"},
                {"kind": "phone", "href": "tel:+15551212", "text": "(555) 512-12"},
                {"kind": "email", "href": "beth@example.com"},
            ],
        },
    )
    kinds = [s.kind for s in updated.heading.ordered_slots()]
    assert kinds[:2] == ["phone", "email"]
    assert updated.heading.name == "Beth Example"


def test_unknown_ids_raise_validation_error():
    store = ResumeStore()
    src = seed_bright(store)
    with pytest.raises(ValidationError):
        update_resume(
            store,
            src.resume_id,
            src.revision,
            "req-bad-bul",
            bullets=[{"bullet_id": "bul_missing", "text": "nope"}],
        )
    with pytest.raises(ValidationError):
        update_resume(
            store,
            src.resume_id,
            src.revision,
            "req-bad-ent",
            entry_fields=[{"entry_id": "ent_missing", "fields": {"company": "X"}}],
        )
    with pytest.raises(ValidationError):
        update_resume(
            store,
            src.resume_id,
            src.revision,
            "req-bad-row",
            skill_rows=[{"row_id": "row_missing", "title": "Nope"}],
        )
    assert get_resume(store, src.resume_id).revision == src.revision


def test_entry_skill_and_coursework_patches():
    store = ResumeStore()
    src = seed_bright(store)
    edu = src.sections[0].entries[0]
    job = src.sections[1].entries[0]
    langs = src.sections[3].skill_rows[0]
    updated = update_resume(
        store,
        src.resume_id,
        src.revision,
        "req-rows",
        entry_fields=[
            {
                "entry_id": job.entry_id,
                "fields": {"company": "Palo Alto Networks", "location": "Santa Clara, CA"},
                "honors": ["Code2040"],
                "header_lines": 1,
            }
        ],
        skill_rows=[{"row_id": langs.row_id, "items": ["Python", "Go"], "wrap_lines": 2}],
        coursework=[{"entry_id": edu.entry_id, "items": ["Operating Systems & Security", "Intro to AI"]}],
    )
    patched_job = updated.sections[1].entries[0]
    assert patched_job.fields["company"] == "Palo Alto Networks"
    assert patched_job.fields["dates"] == "May 2026 -- Aug 2026"
    assert patched_job.honors == ["Code2040"]
    assert patched_job.header_lines == 1
    assert updated.sections[3].skill_rows[0].items == ["Python", "Go"]
    assert updated.sections[3].skill_rows[0].wrap_lines == 2
    assert updated.sections[0].entries[0].coursework == [
        "Operating Systems & Security",
        "Intro to AI",
    ]


def test_update_replay_same_request():
    store = ResumeStore()
    src = seed_bright(store)
    first = update_resume(
        store,
        src.resume_id,
        src.revision,
        "req-replay",
        heading={"name": "Once"},
    )
    second = update_resume(
        store,
        src.resume_id,
        src.revision,
        "req-replay",
        heading={"name": "Once"},
    )
    assert first.revision == second.revision == src.revision + 1
    assert get_resume(store, src.resume_id).heading.name == "Once"
