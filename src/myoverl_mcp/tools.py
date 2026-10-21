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
