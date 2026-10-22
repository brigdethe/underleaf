from myoverl_mcp.store import ResumeStore
from tests.conftest import make_source


def test_store_reloads_from_disk(tmp_path):
    first = ResumeStore(tmp_path)
    resume = make_source("Bright")
    first.put(resume)

    second = ResumeStore(tmp_path)
    loaded = second.get(resume.resume_id)
    assert loaded.heading.name == resume.heading.name
    assert loaded.name == "Bright"
    assert loaded.role == "source"


def test_apply_persists_revision(tmp_path):
    store = ResumeStore(tmp_path)
    resume = make_source()
    store.put(resume)

    def bump(current):
        current.heading.name = "Beth Example"
        return current

    store.apply(resume.resume_id, 1, "req-p", "hash-p", bump)
    reloaded = ResumeStore(tmp_path).get(resume.resume_id)
    assert reloaded.heading.name == "Beth Example"
    assert reloaded.revision == 2
