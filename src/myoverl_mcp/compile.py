from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from myoverl_mcp.models import Entry, Resume, Section

PREAMBLE = r"""
\documentclass[letterpaper,11pt]{article}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\input{glyphtounicode}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\setlength{\oddsidemargin}{\dimexpr SIDEINin-1in\relax}
\setlength{\evensidemargin}{\dimexpr SIDEINin-1in\relax}
\setlength{\textwidth}{\dimexpr\paperwidth-HORIZINin\relax}
\setlength{\topmargin}{\dimexpr TOPINin-1in-\headheight-\headsep\relax}
\setlength{\textheight}{\dimexpr\paperheight-VERTICALin\relax}
\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]
\pdfgentounicode=1
\newcommand{\resumeItem}[1]{
  \item\small{
    {\if\relax\detokenize{#1}\relax\phantom{Edit}\else#1\fi\vspace{-2pt}}
  }
}
\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeProjectHeading}[3]{
    \item
    \begin{tabular*}{\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #3 \\
      \small\emph{#2} & \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeProjectHeadingOneLine}[3]{
    \item
    \begin{tabular*}{\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1\if\relax\detokenize{#2}\relax\else{} $|$ \emph{#2}\fi & #3 \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeCoursework}[1]{
  \item\small{\textnormal{\textbf{Relevant Coursework:} #1}\vspace{-7pt}}
}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
""".strip()


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "<": r"$<$",
        ">": r"$>$",
    }
    out = []
    for char in text:
        out.append(replacements.get(char, char))
    return "".join(out)


def _href(url: str, label: str) -> str:
    return rf"\href{{{url}}}{{\underline{{{latex_escape(label)}}}}}"


class PreviewFields:
    """Attach invisible PDF hit areas without changing the typeset content."""

    def __init__(self) -> None:
        self.fields: dict[str, dict[str, str]] = {}

    def mark(self, tex: str, kind: str, id: str, raw: str, extra: str = "") -> str:
        key = f"f{len(self.fields)}"
        self.fields[key] = {"kind": kind, "id": id, "extra": extra, "raw": raw, "label": extra or kind}
        # A zero-width phantom gives empty fields a hit area without adding ink
        # or affecting line breaking. Empty bullets retain their existing phantom.
        if not tex:
            tex = r"\makebox[0pt][l]{\phantom{Edit}}"
        return rf"\href{{https://myoverl.invalid/edit/{key}}}{{{tex}}}"


def _mark(preview: PreviewFields | None, tex: str, kind: str, id: str, raw: str, extra: str = "") -> str:
    return preview.mark(tex, kind, id, raw, extra) if preview is not None else tex


def _italic_content(tex: str, preview: PreviewFields | None) -> str:
    # A hyperlink's closing whatsit hides the final italic glyph from LaTeX's
    # automatic correction. Preserve that spacing inside the annotation instead.
    return tex + (r"\/" if preview is not None and tex else "")


def _heading(resume: Resume, preview: PreviewFields | None = None) -> str:
    slots = resume.heading.ordered_slots()
    links = " $|$ \n    ".join(
        _mark(preview, rf"\underline{{{latex_escape(slot.text)}}}", "slot-text", slot.slot_id, slot.text)
        if preview is not None else _href(slot.href, slot.text) for slot in slots
    )
    name = _mark(preview, latex_escape(resume.heading.name), "heading-name", "", resume.heading.name)
    return rf"""
\begin{{center}}
    \textbf{{\Huge \scshape {name}}} \\ \vspace{{1pt}}
    \small {links}
\end{{center}}
""".strip()


def _items(entry: Entry, preview: PreviewFields | None = None) -> str:
    if not entry.bullets:
        return ""
    lines = "\n".join(
        r"        \resumeItem{" + _mark(preview, latex_escape(b.text) or (r"\phantom{Edit}" if preview else ""), "bullet", b.bullet_id, b.text) + "}"
        for b in entry.bullets
    )
    return "      \\resumeItemListStart\n" + lines + "\n      \\resumeItemListEnd"


def _education(section: Section, preview: PreviewFields | None = None) -> str:
    parts = ["\\resumeSubHeadingListStart"]
    for entry in section.entries:
        school = latex_escape(entry.fields.get("school", entry.title))
        location = latex_escape(entry.fields.get("location", ""))
        degree = latex_escape(entry.fields.get("degree", entry.title))
        dates = latex_escape(entry.fields.get("dates", ""))
        school = _mark(preview, school, "field", entry.entry_id, entry.fields.get("school", entry.title), "school")
        location = _mark(preview, location, "field", entry.entry_id, entry.fields.get("location", ""), "location")
        degree = _mark(preview, _italic_content(degree, preview), "field", entry.entry_id, entry.fields.get("degree", entry.title), "degree")
        dates = _mark(preview, _italic_content(dates, preview), "field", entry.entry_id, entry.fields.get("dates", ""), "dates")
        parts.append(
            "    \\resumeSubheading\n"
            f"      {{{school}}}{{{location}}}\n"
            f"      {{{degree}}}{{{dates}}}"
        )
        if entry.honors:
            honors = ", ".join(latex_escape(h) for h in entry.honors)
            honors = _mark(preview, honors, "honors", entry.entry_id, ", ".join(entry.honors))
            parts.append(
                r"    \item\small{\textnormal{\textbf{Honors/Associations:} "
                + honors
                + r"}\vspace{-7pt}}"
            )
        if entry.coursework:
            courses = ", ".join(latex_escape(c) for c in entry.coursework)
            courses = _mark(preview, courses, "coursework", entry.entry_id, ", ".join(entry.coursework))
            parts.append(rf"    \resumeCoursework{{{courses}}}")
        if entry.bullets:
            parts.append(_items(entry, preview))
    parts.append("\\resumeSubHeadingListEnd")
    return "\n".join(parts)


def _experience(section: Section, preview: PreviewFields | None = None) -> str:
    parts = ["\\resumeSubHeadingListStart"]
    for entry in section.entries:
        company = latex_escape(entry.fields.get("company", entry.title))
        dates = latex_escape(entry.fields.get("dates", ""))
        title = latex_escape(entry.title)
        location = latex_escape(entry.fields.get("location", ""))
        company = _mark(preview, company, "field", entry.entry_id, entry.fields.get("company", entry.title), "company")
        dates = _mark(preview, dates, "field", entry.entry_id, entry.fields.get("dates", ""), "dates")
        title = _mark(preview, _italic_content(title, preview), "title", entry.entry_id, entry.title)
        location = _mark(preview, _italic_content(location, preview), "field", entry.entry_id, entry.fields.get("location", ""), "location")
        parts.append(
            "    \\resumeSubheading\n"
            f"      {{{company}}}{{{dates}}}\n"
            f"      {{{title}}}{{{location}}}"
        )
        parts.append(_items(entry, preview))
    parts.append("\\resumeSubHeadingListEnd")
    return "\n".join(parts)


def _project_title(title: str) -> str:
    if " (" in title and title.endswith(")"):
        main, rest = title.rsplit(" (", 1)
        return rf"\textbf{{{latex_escape(main)}}} \emph{{({latex_escape(rest)}}}"
    return rf"\textbf{{{latex_escape(title)}}}"


def _projects(section: Section, preview: PreviewFields | None = None) -> str:
    parts = ["\\resumeSubHeadingListStart"]
    for entry in section.entries:
        title = _project_title(entry.title)
        techs = latex_escape(", ".join(entry.technologies))
        label = (entry.link_text or "Link").strip() or "Link"
        link = _href(entry.link_url, label) if entry.link_url else ""
        title = _mark(preview, title, "title", entry.entry_id, entry.title)
        techs = _mark(preview, _italic_content(techs, preview), "techs", entry.entry_id, ", ".join(entry.technologies))
        if preview is not None:
            shown = rf"\underline{{{latex_escape(label)}}}" if entry.link_url else ""
            link = preview.mark(shown, "link", entry.entry_id, entry.link_url or "")
        macro = "\\resumeProjectHeadingOneLine" if entry.header_lines == 1 else "\\resumeProjectHeading"
        parts.append(
            f"      {macro}\n"
            f"          {{{title}}}\n"
            f"          {{{techs}}}\n"
            f"          {{{link}}}"
        )
        parts.append(_items(entry, preview))
    parts.append("\\resumeSubHeadingListEnd")
    return "\n".join(parts)


def _skills(section: Section, preview: PreviewFields | None = None) -> str:
    rows = " \\\\\n     ".join(
        r"\textbf{" + _mark(preview, latex_escape(row.title), "skill-title", row.row_id, row.title)
        + "}{: " + _mark(preview, latex_escape(', '.join(row.items)), "skill-items", row.row_id, ', '.join(row.items)) + "}"
        for row in section.skill_rows
    )
    return (
        " \\begin{itemize}[leftmargin=0in, label={}]\n"
        "    \\small{\\item{\n"
        f"     {rows}\n"
        "    }}\n"
        " \\end{itemize}"
    )


def _extras(section: Section, preview: PreviewFields | None = None) -> str:
    parts = ["\\resumeSubHeadingListStart"]
    for entry in section.entries:
        dates = latex_escape(entry.fields.get("dates", ""))
        dates = _mark(preview, dates, "field", entry.entry_id, entry.fields.get("dates", ""), "dates")
        title = _mark(preview, latex_escape(entry.title), "title", entry.entry_id, entry.title)
        parts.append(
            "    \\vspace{-2pt}\\item\n"
            "      \\begin{tabular*}{\\textwidth}[t]{l@{\\extracolsep{\\fill}}r}\n"
            f"        \\textbf{{{title}}} & {dates} \\\\\n"
            "      \\end{tabular*}\\vspace{-7pt}"
        )
        parts.append(_items(entry, preview))
    parts.append("\\resumeSubHeadingListEnd")
    return "\n".join(parts)


_RENDERERS = {
    "education": _education,
    "experience": _experience,
    "projects": _projects,
    "skills": _skills,
    "extracurriculars": _extras,
}


def render_tex(resume: Resume, preview: PreviewFields | None = None) -> str:
    vertical = resume.page.top_in + resume.page.bottom_in
    horizin = round(2.0 * resume.page.side_in, 4)
    preamble = (
        PREAMBLE.replace("TOPIN", f"{resume.page.top_in}")
        .replace("VERTICAL", f"{vertical}")
        .replace("SIDEIN", f"{resume.page.side_in}")
        .replace("HORIZIN", f"{horizin}")
    )
    body = [_heading(resume, preview)]
    for section in resume.sections:
        renderer = _RENDERERS.get(section.kind)
        if renderer is None:
            continue
        body.append(f"%-----------{section.title.upper()}-----------")
        body.append(rf"\section{{{latex_escape(section.title)}}}")
        body.append(renderer(section, preview))
    return preamble + "\n\n\\begin{document}\n\n" + "\n\n".join(body) + "\n\n\\end{document}\n"


class CompileError(Exception):
    def __init__(self, message: str, log: str = "") -> None:
        super().__init__(message)
        self.log = log


def compile_pdf(resume: Resume, output_pdf: Path) -> Path:
    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_pdf.write_bytes(_compile_tex(render_tex(resume), max_pages=resume.page.max_pages))
    return output_pdf


def compile_preview(resume: Resume) -> tuple[bytes, dict[str, dict[str, str]]]:
    preview = PreviewFields()
    pdf = _compile_tex(render_tex(resume, preview))
    return pdf, preview.fields


def _compile_tex(tex: str, max_pages: int | None = None) -> bytes:
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        raise CompileError("pdflatex is not installed")
    with tempfile.TemporaryDirectory() as raw:
        work = Path(raw)
        source = work / "resume.tex"
        source.write_text(tex, encoding="utf-8")
        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "resume.tex"],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        built = work / "resume.pdf"
        if result.returncode != 0 or not built.exists():
            raise CompileError("pdflatex failed", log=result.stdout + result.stderr)
        pdf_bytes = built.read_bytes()
        if max_pages is not None:
            m = re.search(r"Output written on [^(]+\((\d+)\s+pages?", result.stdout)
            page_count = int(m.group(1)) if m else len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
            if page_count > max_pages:
                raise CompileError(
                    f"Document exceeds maximum allowed pages ({max_pages}): generated {page_count} pages",
                    log=result.stdout,
                )
        return pdf_bytes
