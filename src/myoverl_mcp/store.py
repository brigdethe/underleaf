from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

from myoverl_mcp.errors import ConflictError, NotFoundError
from myoverl_mcp.models import Resume


class ResumeStore:
    def __init__(self, data_dir: Path | str | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir is not None else None
        self._resumes: dict[str, Resume] = {}
        self._replays: dict[tuple[str, str], tuple[str, Resume]] = {}
        self._copy_replays: dict[tuple[str, str], tuple[str, Resume]] = {}
        if self._data_dir is not None:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._load()

    def _resume_path(self, resume_id: str) -> Path:
        assert self._data_dir is not None
        return self._data_dir / f"{resume_id}.json"

    def _load(self) -> None:
        assert self._data_dir is not None
        for path in self._data_dir.glob("*.json"):
            resume = Resume.model_validate_json(path.read_text(encoding="utf-8"))
            self._resumes[resume.resume_id] = resume

    def _persist(self, resume: Resume) -> None:
        if self._data_dir is None:
            return
        self._resume_path(resume.resume_id).write_text(
            resume.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def put(self, resume: Resume) -> Resume:
        stored = deepcopy(resume)
        self._resumes[resume.resume_id] = stored
        self._persist(stored)
        return deepcopy(stored)

    def get(self, resume_id: str) -> Resume:
        try:
            return deepcopy(self._resumes[resume_id])
        except KeyError as exc:
            raise NotFoundError(resume_id) from exc

    def list_all(self) -> list[Resume]:
        return [deepcopy(r) for r in self._resumes.values()]

    def remember_copy(self, source_id: str, request_id: str, args_hash: str, resume: Resume) -> None:
        self._copy_replays[(source_id, request_id)] = (args_hash, deepcopy(resume))

    def lookup_copy(self, source_id: str, request_id: str) -> tuple[str, Resume] | None:
        saved = self._copy_replays.get((source_id, request_id))
        if saved is None:
            return None
        saved_hash, resume = saved
        return saved_hash, deepcopy(resume)

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
        self._persist(updated)
        self._replays[replay_key] = (args_hash, deepcopy(updated))
        return deepcopy(updated)
