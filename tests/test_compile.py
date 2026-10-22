from myoverl_mcp.compile import render_tex
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore


def test_render_tex_includes_heading_and_school():
    store = ResumeStore()
    resume = seed_bright(store)
    tex = render_tex(resume)
    assert r"\textbf{\Huge \scshape Bright Owusu}" in tex
    assert "Grambling State University" in tex
    assert r"linkedin.com/in/owusuomaribright" in tex
    assert "WVS 1.01" in tex
    assert r"\href{https://omariomari2.github.io/webpager/}" in tex
    assert r"\underline{Link}" in tex
    assert r"\textbf{Immigration Assistant} \emph{(Best Overall Project, Code2040 TFR Hackathon)}" in tex
    assert "Google Student Developer" in tex
    assert r"\usepackage[empty]{fullpage}" in tex
    assert r"\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0in, label={}]}" in tex
    assert r"leftmargin=0.15in" not in tex
    assert r"\newcommand{\resumeItemListStart}{\begin{itemize}}" in tex
    assert r"\begin{tabular*}{\textwidth}" in tex
    assert r"0.97\textwidth" not in tex


def test_render_tex_uses_project_link_text_and_omits_hidden_link():
    store = ResumeStore()
    resume = seed_bright(store)
    project = resume.sections[2].entries[0]
    project.link_text = "Demo"
    tex = render_tex(resume)
    assert r"\href{https://omariomari2.github.io/webpager/}{\underline{Demo}}" in tex
    project.link_url = None
    hidden = render_tex(resume)
    assert "omariomari2.github.io" not in hidden
    assert r"\underline{Demo}" not in hidden


def test_render_tex_respects_side_margin_and_project_header_lines():
    store = ResumeStore()
    resume = seed_bright(store)
    resume.page.side_in = 0.4
    resume.sections[2].entries[0].header_lines = 1
    resume.sections[2].entries[1].header_lines = 2
    tex = render_tex(resume)
    assert r"\setlength{\oddsidemargin}{\dimexpr 0.4in-1in\relax}" in tex
    assert r"\setlength{\textwidth}{\dimexpr\paperwidth-0.8in\relax}" in tex
    assert r"\resumeProjectHeadingOneLine" in tex
    assert r"\resumeProjectHeading" in tex


def test_compile_pdf_rejects_multipage_document(tmp_path):
    import shutil
    import pytest
    from myoverl_mcp.compile import CompileError, compile_pdf

    if not shutil.which("pdflatex"):
        pytest.skip("pdflatex not installed")
    store = ResumeStore()
    resume = seed_bright(store)
    # Replicate sections to force multi-page document
    resume.sections = resume.sections * 4
    with pytest.raises(CompileError) as exc_info:
        compile_pdf(resume, tmp_path / "overflow.pdf")
    assert "exceeds maximum allowed pages (1)" in str(exc_info.value)
