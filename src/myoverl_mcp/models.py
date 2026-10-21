from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from myoverl_mcp.ids import new_id

ContactKind = Literal["phone", "email", "linkedin", "github", "portfolio", "other"]
SectionKind = Literal["heading", "education", "experience", "projects", "skills", "extracurriculars"]
ResumeRole = Literal["source", "copy"]


def format_gpa(value: str) -> str:
    raw = value.strip()
    if raw.lower().startswith("gpa:"):
        number = raw.split(":", 1)[1].strip()
        return f"GPA: {number}"
    return f"GPA: {raw}"


def _host_path(href: str) -> str:
    parsed = urlparse(href)
    host = (parsed.netloc or "").removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def stencil_contact(*, kind: ContactKind, href: str, text: str | None) -> ContactSlot:
    href = href.strip()
    if kind == "phone":
        display = text or href.removeprefix("tel:")
        if not href.startswith("tel:"):
            href = "tel:" + href
        return ContactSlot(slot_id=new_id("slot"), kind=kind, href=href, text=display)
    if kind == "email":
        display = text or href.removeprefix("mailto:")
        if not href.startswith("mailto:"):
            href = "mailto:" + href
        return ContactSlot(slot_id=new_id("slot"), kind=kind, href=href, text=display)
    if kind == "linkedin":
        return ContactSlot(slot_id=new_id("slot"), kind=kind, href=href, text=text or _host_path(href).removeprefix("www."))
    if kind == "github":
        return ContactSlot(slot_id=new_id("slot"), kind=kind, href=href, text=text or _host_path(href))
    if kind == "portfolio":
        return ContactSlot(slot_id=new_id("slot"), kind=kind, href=href, text=text or "Portfolio")
    return ContactSlot(slot_id=new_id("slot"), kind=kind, href=href, text=text or _host_path(href))


class ContactSlot(BaseModel):
    slot_id: str
    kind: ContactKind
    href: str
    text: str


class Heading(BaseModel):
    name: str
    slots: list[ContactSlot] = Field(default_factory=list)

    def ordered_slots(self) -> list[ContactSlot]:
        first = [s for s in self.slots if s.kind in ("phone", "email")]
        rest = [s for s in self.slots if s.kind not in ("phone", "email")]
        phones = [s for s in first if s.kind == "phone"]
        emails = [s for s in first if s.kind == "email"]
        return phones + emails + rest


class Bullet(BaseModel):
    bullet_id: str
    text: str


class Entry(BaseModel):
    entry_id: str
    kind: Literal["education", "experience", "project", "extracurricular"]
    title: str
    fields: dict[str, str] = Field(default_factory=dict)
    bullets: list[Bullet] = Field(default_factory=list)
    coursework: list[str] = Field(default_factory=list)
    honors: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    link_url: str | None = None
    header_lines: Literal[1, 2] = 2


class SkillRow(BaseModel):
    row_id: str
    title: str
    items: list[str] = Field(default_factory=list)
    wrap_lines: Literal[1, 2] = 1


class Section(BaseModel):
    section_id: str
    kind: SectionKind
    title: str
    entries: list[Entry] = Field(default_factory=list)
    skill_rows: list[SkillRow] = Field(default_factory=list)


class PageSettings(BaseModel):
    top_in: float = 0.15
    bottom_in: float = 0.15
    side_in: float = 0.5
    max_pages: Literal[1] = 1

    @model_validator(mode="after")
    def match_vertical(self) -> PageSettings:
        if self.top_in != self.bottom_in:
            raise ValueError("top and bottom margins must match")
        return self


class Resume(BaseModel):
    resume_id: str
    name: str
    role: ResumeRole
    source_id: str | None = None
    revision: int = 1
    editor_url: str = ""
    page: PageSettings = Field(default_factory=PageSettings)
    heading: Heading
    sections: list[Section] = Field(default_factory=list)


class ResumeSummary(BaseModel):
    resume_id: str
    name: str
    role: ResumeRole
    revision: int
    editor_url: str
