from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from myoverl_mcp.errors import ConflictError, NotFoundError
from myoverl_mcp.models import Resume


class ResumeStore:
    def __init__(self) -> None:
        self._resumes: dict[str, Resume] = {}
        self._replays: dict[tuple[str, str], tuple[str, Resume]] = {}

    def put(self, resume: Resume) -> Resume:
        self._resumes[resume.resume_id] = resume
        return resume

    def get(self, resume_id: str) -> Resume:
        try:
            return deepcopy(self._resumes[resume_id])
        except KeyError as exc:
            raise NotFoundError(resume_id) from exc

    def list_all(self) -> list[Resume]:
        return [deepcopy(r) for r in self._resumes.values()]

    def apply(
        self,
        resume_id: str,
        base_revision: int,
        request_id: str,
        args_hash: str,
        mutate: Callable[[Resume], Resume],
    ) -> Resume:
        current = self.get(resume_id)
        replay_key = (resume_id, request_id)
        if replay_key in self._replays:
            saved_hash, saved = self._replays[replay_key]
            if saved_hash == args_hash:
                return deepcopy(saved)
        if current.revision != base_revision:
            raise ConflictError(current.revision)
        updated = mutate(current)
        updated.revision = current.revision + 1
        self._resumes[resume_id] = updated
        self._replays[replay_key] = (args_hash, deepcopy(updated))
        return deepcopy(updated)
