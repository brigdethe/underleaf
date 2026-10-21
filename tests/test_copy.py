from myoverl_mcp.errors import ConflictError
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore
from myoverl_mcp.tools import copy_resume, get_resume
import pytest


def test_copy_leaves_source_untouched():
    store = ResumeStore()
    src = seed_bright(store)
    copied = copy_resume(store, src.resume_id, src.revision, "req-copy", "PANW intern")
    assert copied.role == "copy"
    assert copied.source_id == src.resume_id
    assert copied.name == "PANW intern"
    assert get_resume(store, src.resume_id).revision == src.revision
    assert copied.resume_id != src.resume_id


def test_copy_conflict():
    store = ResumeStore()
    src = seed_bright(store)
    with pytest.raises(ConflictError):
        copy_resume(store, src.resume_id, 99, "req-x", "Nope")


def test_copy_replay():
    store = ResumeStore()
    src = seed_bright(store)
    a = copy_resume(store, src.resume_id, src.revision, "req-dup", "Same")
    b = copy_resume(store, src.resume_id, src.revision, "req-dup", "Same")
    assert a.resume_id == b.resume_id


def test_copy_same_request_id_different_name_conflicts():
    store = ResumeStore()
    src = seed_bright(store)
    first = copy_resume(store, src.resume_id, src.revision, "req-dup", "Same")
    with pytest.raises(ConflictError):
        copy_resume(store, src.resume_id, src.revision, "req-dup", "Other")
    stored = get_resume(store, first.resume_id)
    assert stored.name == "Same"
    assert get_resume(store, src.resume_id).revision == src.revision
