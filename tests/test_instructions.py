import asyncio

from myoverl_mcp.seed import seed_bright
from myoverl_mcp.server import make_server
from myoverl_mcp.store import ResumeStore


MUST_CONTAIN = (
    "copy_resume",
    "Never invent",
    "Ask",
    "Propose",
    "Never",
    "GPA: 3.72",
    "Never 2 pages",
    "phone",
    "email",
    "Impact",
    "Bright",
    "Beth",
    "tools persist",
    "95–110",
    "103",
)

MUST_NOT_CONTAIN = (
    "preserve_exact",
    "chatgpt.site",
    "they may invent",
)


def _server():
    store = ResumeStore()
    seed_bright(store)
    return make_server(store)


def test_server_instructions_carry_locked_rules():
    server = _server()
    text = server.instructions or ""
    lowered = text.lower()
    for needle in MUST_CONTAIN:
        assert needle.lower() in lowered, needle
    for banned in MUST_NOT_CONTAIN:
        assert banned.lower() not in lowered, banned


def test_tailor_prompt_is_registered():
    server = _server()
    prompts = asyncio.run(server.list_prompts())
    by_name = {p.name: p for p in prompts}
    assert "tailor" in by_name
    names = {a.name for a in (by_name["tailor"].arguments or [])}
    assert "job" in names


def test_tailor_prompt_renders_job_and_copy_first():
    server = _server()
    result = asyncio.run(
        server.get_prompt("tailor", {"job": "https://example.invalid/intern", "resume_name": "Beth"})
    )
    body = " ".join(
        block.text
        for message in result.messages
        for block in ([message.content] if not isinstance(message.content, list) else message.content)
        if getattr(block, "text", None)
    )
    if not body:
        body = str(result.messages)
    assert "https://example.invalid/intern" in body
    assert "Beth" in body
    assert "copy_resume" in body
