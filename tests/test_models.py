from myoverl_mcp.models import ContactSlot, Heading, PageSettings, format_gpa, stencil_contact


def test_gpa_format():
    assert format_gpa("3.72") == "GPA: 3.72"


def test_phone_slot_keeps_tel_and_display():
    slot = stencil_contact(kind="phone", href="tel:+13182658445", text="(318) 265-8445")
    assert slot.href == "tel:+13182658445"
    assert slot.text == "(318) 265-8445"


def test_linkedin_text_strips_scheme():
    slot = stencil_contact(
        kind="linkedin",
        href="https://www.linkedin.com/in/owusuomaribright",
        text=None,
    )
    assert slot.text == "linkedin.com/in/owusuomaribright"


def test_portfolio_label():
    slot = stencil_contact(kind="portfolio", href="https://omari.is-a.dev", text=None)
    assert slot.text == "Portfolio"


def test_other_site_strips_scheme_www_slash():
    slot = stencil_contact(kind="other", href="https://www.example.com/x/", text=None)
    assert slot.text == "example.com/x"


def test_page_margins_must_match():
    page = PageSettings(top_in=0.15, bottom_in=0.15, side_in=0.5)
    assert page.top_in == page.bottom_in
