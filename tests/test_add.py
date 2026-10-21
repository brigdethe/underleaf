from myoverl_mcp.errors import ValidationError
from myoverl_mcp.ids import new_id
from myoverl_mcp.models import Heading, Resume
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore
from myoverl_mcp.tools import add_experience, add_project, get_resume
import pytest


def test_add_experience_appends():
    store = ResumeStore()
    src = seed_bright(store)
    out = add_experience(
        store,
        src.resume_id,
        src.revision,
        "req-ae",
        company="Acme",
        title="Intern",
        dates="May 2024 -- Aug 2024",
        location="Remote",
        bullets=["Wrote e2e tests for 12 transaction and balance paths with Spring Boot Test."],
    )
    jobs = next(s for s in out.sections if s.kind == "experience")
    assert jobs.entries[-1].fields["company"] == "Acme"


def test_add_project_without_link():
    store = ResumeStore()
    src = seed_bright(store)
    out = add_project(
        store,
        src.resume_id,
        src.revision,
        "req-ap",
        title="Lab Bench",
        technologies=["Python"],
        link_url=None,
        bullets=["Built a local scanner that flagged 8 unsafe eval calls in one repo."],
    )
    projects = next(s for s in out.sections if s.kind == "projects")
    assert projects.entries[-1].link_url is None


def test_add_experience_sets_fields_title_and_bullets():
    store = ResumeStore()
    src = seed_bright(store)
    jobs = next(s for s in src.sections if s.kind == "experience")
    original_ids = [e.entry_id for e in jobs.entries]
    out = add_experience(
        store,
        src.resume_id,
        src.revision,
        "req-ae-fields",
        company="Acme",
        title="Intern",
        dates="May 2024 -- Aug 2024",
        location="Remote",
        bullets=["Wrote e2e tests for 12 transaction and balance paths with Spring Boot Test."],
    )
    got = next(s for s in out.sections if s.kind == "experience")
    added = got.entries[-1]
    assert [e.entry_id for e in got.entries[:-1]] == original_ids
    assert added.kind == "experience"
    assert added.title == "Intern"
    assert added.fields == {
        "company": "Acme",
        "dates": "May 2024 -- Aug 2024",
        "location": "Remote",
    }
    assert [b.text for b in added.bullets] == [
        "Wrote e2e tests for 12 transaction and balance paths with Spring Boot Test."
    ]


def test_add_project_keeps_technologies_and_omits_missing_link():
    store = ResumeStore()
    src = seed_bright(store)
    out = add_project(
        store,
        src.resume_id,
        src.revision,
        "req-ap-tech",
        title="Lab Bench",
        technologies=["Python"],
        link_url=None,
        bullets=["Built a local scanner that flagged 8 unsafe eval calls in one repo."],
    )
    added = next(s for s in out.sections if s.kind == "projects").entries[-1]
    assert added.kind == "project"
    assert added.title == "Lab Bench"
    assert added.technologies == ["Python"]
    assert added.link_url is None


def test_add_project_with_link_url():
    store = ResumeStore()
    src = seed_bright(store)
    out = add_project(
        store,
        src.resume_id,
        src.revision,
        "req-ap-link",
        title="Lab Bench",
        technologies=None,
        link_url="https://example.invalid/lab",
        bullets=["Built a local scanner that flagged 8 unsafe eval calls in one repo."],
    )
    added = next(s for s in out.sections if s.kind == "projects").entries[-1]
    assert added.link_url == "https://example.invalid/lab"
    assert added.technologies == []


def test_add_assigns_new_entry_and_bullet_ids():
    store = ResumeStore()
    src = seed_bright(store)
    existing = {
        e.entry_id
        for s in src.sections
        for e in s.entries
    }
    existing_bullets = {
        b.bullet_id
        for s in src.sections
        for e in s.entries
        for b in e.bullets
    }
    out = add_experience(
        store,
        src.resume_id,
        src.revision,
        "req-ids",
        company="Acme",
        title="Intern",
        dates="May 2024 -- Aug 2024",
        location="Remote",
        bullets=["Wrote e2e tests for 12 transaction and balance paths with Spring Boot Test."],
    )
    added = next(s for s in out.sections if s.kind == "experience").entries[-1]
    assert added.entry_id.startswith("ent_")
    assert added.entry_id not in existing
    assert len(added.bullets) == 1
    assert added.bullets[0].bullet_id.startswith("bul_")
    assert added.bullets[0].bullet_id not in existing_bullets


def test_add_is_idempotent_for_same_request_id():
    store = ResumeStore()
    src = seed_bright(store)
    first = add_experience(
        store,
        src.resume_id,
        src.revision,
        "req-replay",
        company="Acme",
        title="Intern",
        dates="May 2024 -- Aug 2024",
        location="Remote",
        bullets=["Wrote e2e tests for 12 transaction and balance paths with Spring Boot Test."],
    )
    second = add_experience(
        store,
        src.resume_id,
        src.revision,
        "req-replay",
        company="Acme",
        title="Intern",
        dates="May 2024 -- Aug 2024",
        location="Remote",
        bullets=["Wrote e2e tests for 12 transaction and balance paths with Spring Boot Test."],
    )
    jobs = next(s for s in get_resume(store, src.resume_id).sections if s.kind == "experience")
    assert first.revision == second.revision == src.revision + 1
    assert first.sections[1].entries[-1].entry_id == second.sections[1].entries[-1].entry_id
    assert len(jobs.entries) == 4


def test_add_rejects_bad_title_and_bullets():
    store = ResumeStore()
    src = seed_bright(store)
    ok = ["Wrote e2e tests for 12 transaction and balance paths with Spring Boot Test."]
    with pytest.raises(ValidationError):
        add_experience(
            store,
            src.resume_id,
            src.revision,
            "req-empty",
            company="Acme",
            title="Intern",
            dates="May 2024 -- Aug 2024",
            location="Remote",
            bullets=[],
        )
    with pytest.raises(ValidationError):
        add_project(
            store,
            src.resume_id,
            src.revision,
            "req-nine",
            title="Lab Bench",
            technologies=["Python"],
            link_url=None,
            bullets=[f"Bullet {i} with a nonempty claim about work." for i in range(9)],
        )
    with pytest.raises(ValidationError):
        add_experience(
            store,
            src.resume_id,
            src.revision,
            "req-blank",
            company="Acme",
            title="Intern",
            dates="May 2024 -- Aug 2024",
            location="Remote",
            bullets=["", "Wrote e2e tests for 12 transaction and balance paths with Spring Boot Test."],
        )
    with pytest.raises(ValidationError):
        add_project(
            store,
            src.resume_id,
            src.revision,
            "req-title",
            title="T" * 251,
            technologies=["Python"],
            link_url=None,
            bullets=ok,
        )
    assert get_resume(store, src.resume_id).revision == src.revision


def test_add_requires_matching_section():
    store = ResumeStore()
    src = Resume(
        resume_id=new_id("res"),
        name="Bright",
        role="source",
        heading=Heading(name="Bright Owusu"),
        editor_url="https://example.invalid/r/pending",
    )
    store.put(src)
    with pytest.raises(ValidationError):
        add_experience(
            store,
            src.resume_id,
            src.revision,
            "req-no-sec",
            company="Acme",
            title="Intern",
            dates="May 2024 -- Aug 2024",
            location="Remote",
            bullets=["Wrote e2e tests for 12 transaction and balance paths with Spring Boot Test."],
        )
    with pytest.raises(ValidationError):
        add_project(
            store,
            src.resume_id,
            src.revision,
            "req-no-proj",
            title="Lab Bench",
            technologies=["Python"],
            link_url=None,
            bullets=["Built a local scanner that flagged 8 unsafe eval calls in one repo."],
        )
    assert get_resume(store, src.resume_id).revision == src.revision
