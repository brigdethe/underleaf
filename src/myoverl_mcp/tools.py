from copy import deepcopy

from myoverl_mcp.errors import ConflictError
from myoverl_mcp.ids import new_id
from myoverl_mcp.models import Resume, ResumeSummary
from myoverl_mcp.store import ResumeStore


def list_resumes(store: ResumeStore) -> list[ResumeSummary]:
    return [
        ResumeSummary(
            resume_id=r.resume_id,
            name=r.name,
            role=r.role,
            revision=r.revision,
            editor_url=r.editor_url,
        )
        for r in store.list_all()
    ]


def get_resume(store: ResumeStore, resume_id: str) -> Resume:
    return store.get(resume_id)


def copy_resume(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    copy_name: str,
) -> Resume:
    src = store.get(resume_id)
    replayed = store.lookup_copy(src.resume_id, request_id)
    if replayed is not None:
        return replayed
    if src.revision != base_revision:
        raise ConflictError(src.revision)
    copied = src.model_copy(deep=True)
    copied.resume_id = new_id("res")
    copied.role = "copy"
    copied.source_id = src.resume_id
    copied.name = copy_name
    copied.revision = 1
    copied.editor_url = f"https://example.invalid/r/{copied.resume_id}"
    store.put(copied)
    store.remember_copy(src.resume_id, request_id, copied)
    return deepcopy(copied)
