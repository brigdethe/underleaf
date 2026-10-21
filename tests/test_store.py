import pytest

from myoverl_mcp.errors import ConflictError, NotFoundError
from myoverl_mcp.store import ResumeStore
from tests.conftest import make_source


def test_get_missing_raises():
    store = ResumeStore()
    with pytest.raises(NotFoundError):
        store.get("res_missing")


def test_conflict_on_stale_revision(store):
    resume = make_source()
    store.put(resume)

    def bump(r):
        r.heading.name = "X"
        return r

    store.apply(resume.resume_id, 1, "req-1", "hash-a", bump)
    with pytest.raises(ConflictError) as err:
        store.apply(resume.resume_id, 1, "req-2", "hash-b", bump)
    assert err.value.current_revision == 2


def test_same_request_id_and_args_replays(store):
    resume = make_source()
    store.put(resume)

    def bump(r):
        r.heading.name = "Once"
        return r

    first = store.apply(resume.resume_id, 1, "req-same", "hash-same", bump)
    second = store.apply(resume.resume_id, 1, "req-same", "hash-same", bump)
    assert first.revision == second.revision == 2
    assert store.get(resume.resume_id).heading.name == "Once"
