from collections import Counter
import hashlib
import json
import os

from myoverl_mcp.errors import ConflictError, SourceProtectedError, ValidationError
from myoverl_mcp.ids import new_id
from myoverl_mcp.models import Bullet, Entry, Heading, Resume, ResumeSummary, Section, SkillRow, stencil_contact
from myoverl_mcp.store import ResumeStore


def editor_url_for(resume_id: str) -> str:
    base = os.environ.get("MYOVERL_PUBLIC_BASE", "http://127.0.0.1:8765").rstrip("/")
    return f"{base}/?resume={resume_id}"


def _public(resume: Resume) -> Resume:
    resume.editor_url = editor_url_for(resume.resume_id)
    return resume


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _guard_patch(mutate):
    def wrapped(resume: Resume) -> Resume:
        try:
            return mutate(resume)
        except (KeyError, TypeError) as exc:
            raise ValidationError(str(exc)) from exc

    return wrapped


def _require_permutation(actual: list[str], requested: list[str], label: str) -> None:
    if Counter(requested) != Counter(actual):
        raise ValidationError(f"invalid {label} permutation")


def list_resumes(store: ResumeStore) -> list[ResumeSummary]:
    return [
        ResumeSummary(
            resume_id=r.resume_id,
            name=r.name,
            role=r.role,
            revision=r.revision,
            editor_url=editor_url_for(r.resume_id),
        )
        for r in store.list_all()
    ]


def get_resume(store: ResumeStore, resume_id: str) -> Resume:
    return _public(store.get(resume_id))


def copy_resume(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    copy_name: str,
) -> Resume:
    digest = _hash({"copy_name": copy_name, "base_revision": base_revision})
    src = store.get(resume_id)
    saved = store.lookup_copy(src.resume_id, request_id)
    if saved is not None:
        saved_hash, replayed = saved
        if saved_hash == digest:
            return replayed
        raise ConflictError(src.revision)
    if src.revision != base_revision:
        raise ConflictError(src.revision)
    copied = src.model_copy(deep=True)
    copied.resume_id = new_id("res")
    copied.role = "copy"
    copied.source_id = src.resume_id
    copied.name = copy_name
    copied.revision = 1
    copied.editor_url = editor_url_for(copied.resume_id)
    stored = store.put(copied)
    store.remember_copy(src.resume_id, request_id, digest, copied)
    return _public(stored)


def update_resume(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    heading: dict | None = None,
    bullets: list[dict] | None = None,
    entry_fields: list[dict] | None = None,
    skill_rows: list[dict] | None = None,
    coursework: list[dict] | None = None,
) -> Resume:
    digest = _hash(
        {
            "heading": heading,
            "bullets": bullets,
            "entry_fields": entry_fields,
            "skill_rows": skill_rows,
            "coursework": coursework,
        }
    )

    def mutate(resume: Resume) -> Resume:
        if heading is not None:
            if "name" in heading:
                resume.heading.name = heading["name"]
            if "slots" in heading:
                rebuilt = [
                    stencil_contact(
                        kind=slot["kind"],
                        href=slot["href"],
                        text=slot.get("text"),
                    )
                    for slot in heading["slots"]
                ]
                resume.heading.slots = Heading(
                    name=resume.heading.name,
                    slots=rebuilt,
                ).ordered_slots()

        if bullets:
            by_id = {
                bullet.bullet_id: bullet
                for section in resume.sections
                for entry in section.entries
                for bullet in entry.bullets
            }
            for patch in bullets:
                bullet = by_id.get(patch["bullet_id"])
                if bullet is None:
                    raise ValidationError(f"unknown bullet_id: {patch['bullet_id']}")
                bullet.text = patch["text"]

        entries_by_id = {
            entry.entry_id: entry
            for section in resume.sections
            for entry in section.entries
        }

        if entry_fields:
            for patch in entry_fields:
                entry = entries_by_id.get(patch["entry_id"])
                if entry is None:
                    raise ValidationError(f"unknown entry_id: {patch['entry_id']}")
                if "title" in patch:
                    entry.title = patch["title"]
                if "fields" in patch:
                    entry.fields.update(patch["fields"])
                if "honors" in patch:
                    entry.honors = list(patch["honors"])
                if "technologies" in patch:
                    entry.technologies = list(patch["technologies"])
                if "link_url" in patch:
                    entry.link_url = patch["link_url"] or None
                if "link_text" in patch:
                    text = (patch["link_text"] or "").strip()
                    entry.link_text = text or None
                if "header_lines" in patch:
                    entry.header_lines = patch["header_lines"]

        if skill_rows:
            rows_by_id = {
                row.row_id: row
                for section in resume.sections
                for row in section.skill_rows
            }
            for patch in skill_rows:
                row = rows_by_id.get(patch["row_id"])
                if row is None:
                    raise ValidationError(f"unknown row_id: {patch['row_id']}")
                if "title" in patch:
                    row.title = patch["title"]
                if "items" in patch:
                    row.items = list(patch["items"])
                if "wrap_lines" in patch:
                    row.wrap_lines = patch["wrap_lines"]

        if coursework:
            for patch in coursework:
                entry = entries_by_id.get(patch["entry_id"])
                if entry is None:
                    raise ValidationError(f"unknown entry_id: {patch['entry_id']}")
                entry.coursework = list(patch["items"])

        return resume

    return store.apply(resume_id, base_revision, request_id, digest, _guard_patch(mutate))


def reorder_resume(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    section_ids: list[str] | None = None,
    entry_orders: list[dict] | None = None,
    skill_row_ids: list[str] | None = None,
    skill_items: list[dict] | None = None,
) -> Resume:
    if (
        section_ids is None
        and entry_orders is None
        and skill_row_ids is None
        and skill_items is None
    ):
        raise ValidationError("at least one reorder argument is required")

    digest = _hash(
        {
            "section_ids": section_ids,
            "entry_orders": entry_orders,
            "skill_row_ids": skill_row_ids,
            "skill_items": skill_items,
        }
    )

    def mutate(resume: Resume) -> Resume:
        if section_ids is not None:
            by_id = {section.section_id: section for section in resume.sections}
            _require_permutation(list(by_id), section_ids, "section_ids")
            resume.sections = [by_id[sid] for sid in section_ids]

        if entry_orders is not None:
            sections_by_id = {section.section_id: section for section in resume.sections}
            for order in entry_orders:
                section = sections_by_id.get(order["section_id"])
                if section is None:
                    raise ValidationError(f"unknown section_id: {order['section_id']}")
                entries_by_id = {entry.entry_id: entry for entry in section.entries}
                requested = order["entry_ids"]
                _require_permutation(list(entries_by_id), requested, "entry_ids")
                section.entries = [entries_by_id[eid] for eid in requested]

        if skill_row_ids is not None:
            rows_by_id = {
                row.row_id: row
                for section in resume.sections
                for row in section.skill_rows
            }
            _require_permutation(list(rows_by_id), skill_row_ids, "skill_row_ids")
            for section in resume.sections:
                if not section.skill_rows:
                    continue
                owned = {row.row_id for row in section.skill_rows}
                section.skill_rows = [
                    rows_by_id[rid] for rid in skill_row_ids if rid in owned
                ]

        if skill_items is not None:
            rows_by_id = {
                row.row_id: row
                for section in resume.sections
                for row in section.skill_rows
            }
            for patch in skill_items:
                row = rows_by_id.get(patch["row_id"])
                if row is None:
                    raise ValidationError(f"unknown row_id: {patch['row_id']}")
                _require_permutation(row.items, patch["items"], "skill_items")
                row.items = list(patch["items"])

        return resume

    return store.apply(resume_id, base_revision, request_id, digest, _guard_patch(mutate))


def _require_new_entry(title: str, bullets: list[str]) -> None:
    if len(title) > 250:
        raise ValidationError("title must be at most 250 characters")
    if not 1 <= len(bullets) <= 8:
        raise ValidationError("must supply 1 to 8 bullets")
    if any(not bullet.strip() for bullet in bullets):
        raise ValidationError("each bullet must be nonempty")


def _section_of(resume: Resume, kind: str) -> Section:
    for section in resume.sections:
        if section.kind == kind:
            return section
    raise ValidationError(f"missing {kind} section")


def _new_bullets(texts: list[str]) -> list[Bullet]:
    return [Bullet(bullet_id=new_id("bul"), text=text) for text in texts]


def add_experience(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    company: str,
    title: str,
    dates: str,
    location: str,
    bullets: list[str],
) -> Resume:
    _require_new_entry(title, bullets)
    digest = _hash(
        {
            "company": company,
            "title": title,
            "dates": dates,
            "location": location,
            "bullets": bullets,
        }
    )

    def mutate(resume: Resume) -> Resume:
        section = _section_of(resume, "experience")
        section.entries.append(
            Entry(
                entry_id=new_id("ent"),
                kind="experience",
                title=title,
                fields={
                    "company": company,
                    "dates": dates,
                    "location": location,
                },
                bullets=_new_bullets(bullets),
            )
        )
        return resume

    return store.apply(resume_id, base_revision, request_id, digest, mutate)


def add_project(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    title: str,
    technologies: list[str] | None,
    link_url: str | None,
    bullets: list[str],
    link_text: str | None = None,
) -> Resume:
    _require_new_entry(title, bullets)
    techs = list(technologies or [])
    label = (link_text or "").strip() or None
    digest = _hash(
        {
            "title": title,
            "technologies": techs,
            "link_url": link_url,
            "link_text": label,
            "bullets": bullets,
        }
    )

    def mutate(resume: Resume) -> Resume:
        section = _section_of(resume, "projects")
        section.entries.append(
            Entry(
                entry_id=new_id("ent"),
                kind="project",
                title=title,
                technologies=techs,
                link_url=link_url,
                link_text=label,
                bullets=_new_bullets(bullets),
            )
        )
        return resume

    return store.apply(resume_id, base_revision, request_id, digest, mutate)


def add_skill_row(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    title: str,
    items: list[str],
) -> Resume:
    digest = _hash({"title": title, "items": items})

    def mutate(resume: Resume) -> Resume:
        section = _section_of(resume, "skills")
        section.skill_rows.append(
            SkillRow(
                row_id=new_id("row"),
                title=title,
                items=list(items),
            )
        )
        return resume

    return store.apply(resume_id, base_revision, request_id, digest, mutate)


def add_skill_items(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    row_id: str,
    items: list[str],
) -> Resume:
    digest = _hash({"row_id": row_id, "items": items})

    def mutate(resume: Resume) -> Resume:
        rows_by_id = {
            row.row_id: row
            for section in resume.sections
            for row in section.skill_rows
        }
        row = rows_by_id.get(row_id)
        if row is None:
            raise ValidationError(f"unknown row_id: {row_id}")
        seen = set(row.items)
        for item in items:
            if item not in seen:
                row.items.append(item)
                seen.add(item)
        return resume

    return store.apply(resume_id, base_revision, request_id, digest, mutate)


def remove_entry(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    entry_id: str,
) -> Resume:
    digest = _hash({"entry_id": entry_id})

    def mutate(resume: Resume) -> Resume:
        for section in resume.sections:
            for index, entry in enumerate(section.entries):
                if entry.entry_id != entry_id:
                    continue
                if resume.role == "source" and entry.kind in ("experience", "project"):
                    raise SourceProtectedError()
                if entry.kind == "education":
                    remaining = sum(
                        1
                        for candidate_section in resume.sections
                        for candidate in candidate_section.entries
                        if candidate.kind == "education"
                    )
                    if remaining <= 1:
                        raise ValidationError("cannot remove the last education entry")
                section.entries.pop(index)
                return resume
        raise ValidationError(f"unknown entry_id: {entry_id}")

    return store.apply(resume_id, base_revision, request_id, digest, mutate)


def set_layout(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    top_in: float | None = None,
    bottom_in: float | None = None,
    side_in: float | None = None,
    project_header_lines: int | None = None,
    hide_section_ids: list[str] | None = None,
) -> Resume:
    digest = _hash(
        {
            "top_in": top_in,
            "bottom_in": bottom_in,
            "side_in": side_in,
            "project_header_lines": project_header_lines,
            "hide_section_ids": hide_section_ids,
        }
    )

    def mutate(resume: Resume) -> Resume:
        if hide_section_ids and resume.role == "source":
            raise SourceProtectedError()

        if top_in is not None or bottom_in is not None:
            if top_in is not None and bottom_in is not None and top_in != bottom_in:
                raise ValidationError("top and bottom margins must match")
            value = top_in if top_in is not None else bottom_in
            resume.page.top_in = value
            resume.page.bottom_in = value
        if side_in is not None:
            resume.page.side_in = side_in

        if project_header_lines is not None:
            if project_header_lines not in (1, 2):
                raise ValidationError("project_header_lines must be 1 or 2")
            for section in resume.sections:
                for entry in section.entries:
                    if entry.kind == "project":
                        entry.header_lines = project_header_lines

        if hide_section_ids is not None:
            by_id = {section.section_id: section for section in resume.sections}
            for section_id in hide_section_ids:
                if section_id not in by_id:
                    raise ValidationError(f"unknown section_id: {section_id}")
            hidden = set(hide_section_ids)
            resume.sections = [
                section for section in resume.sections if section.section_id not in hidden
            ]

        return resume

    return store.apply(resume_id, base_revision, request_id, digest, mutate)


def add_person(
    store: ResumeStore,
    from_resume_id: str,
    base_revision: int,
    request_id: str,
    person_name: str,
    heading_name: str,
) -> Resume:
    person_name = person_name.strip()
    heading_name = heading_name.strip()
    if not person_name or not heading_name:
        raise ValidationError("person name and heading are required")
    digest = _hash(
        {
            "person_name": person_name,
            "heading_name": heading_name,
            "base_revision": base_revision,
        }
    )
    src = store.get(from_resume_id)
    saved = store.lookup_copy(src.resume_id, request_id)
    if saved is not None:
        saved_hash, replayed = saved
        if saved_hash == digest:
            return _public(replayed)
        raise ConflictError(src.revision)
    if src.revision != base_revision:
        raise ConflictError(src.revision)
    created = src.model_copy(deep=True)
    created.resume_id = new_id("res")
    created.role = "source"
    created.source_id = None
    created.name = person_name
    created.heading.name = heading_name
    created.revision = 1
    created.editor_url = editor_url_for(created.resume_id)
    stored = store.put(created)
    store.remember_copy(src.resume_id, request_id, digest, created)
    return _public(stored)


def rename_resume(
    store: ResumeStore,
    resume_id: str,
    base_revision: int,
    request_id: str,
    name: str,
) -> Resume:
    label = name.strip()
    if not label:
        raise ValidationError("name is required")
    digest = _hash({"name": label})

    def mutate(resume: Resume) -> Resume:
        resume.name = label
        return resume

    return _public(store.apply(resume_id, base_revision, request_id, digest, mutate))

