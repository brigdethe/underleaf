import asyncio

from myoverl_mcp.seed import seed_bright
from myoverl_mcp.server import TOOL_NAMES, make_server
from myoverl_mcp.store import ResumeStore
import pytest

try:
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp.exceptions import ToolError


def test_tool_names():
    store = ResumeStore()
    seed_bright(store)
    server = make_server(store)
    assert set(TOOL_NAMES) == {
        "list_resumes",
        "get_resume",
        "copy_resume",
        "update_resume",
        "reorder_resume",
        "add_experience",
        "add_project",
        "add_skill_row",
        "add_skill_items",
        "remove_entry",
        "set_layout",
    }
    assert hasattr(server, "list_tools") or hasattr(server, "_tool_manager")


def _registered_names(server) -> set[str]:
    if hasattr(server, "_tool_manager"):
        return {tool.name for tool in server._tool_manager.list_tools()}
    return {tool.name for tool in asyncio.run(server.list_tools())}


def _call(server, name: str, arguments: dict | None = None):
    return asyncio.run(server.call_tool(name, arguments or {}))


def test_registered_tools_match_tool_names():
    store = ResumeStore()
    seed_bright(store)
    server = make_server(store)
    assert _registered_names(server) == set(TOOL_NAMES)
    tools = {tool.name: tool for tool in server._tool_manager.list_tools()}
    for tool in tools.values():
        properties = tool.parameters.get("properties", {})
        assert "store" not in properties
    layout_required = set(tools["set_layout"].parameters.get("required", []))
    update_required = set(tools["update_resume"].parameters.get("required", []))
    assert layout_required == {"resume_id", "base_revision", "request_id"}
    assert "hide_section_ids" not in layout_required
    assert "heading" not in update_required


def test_list_resumes_via_server():
    store = ResumeStore()
    seed_bright(store)
    server = make_server(store)
    result = _call(server, "list_resumes")
    assert result.is_error is False
    names = [row["name"] for row in result.structured_content["result"]]
    assert names == ["Bright"]


def _wvs(resume: dict) -> dict:
    return next(
        entry
        for section in resume["sections"]
        if section["kind"] == "projects"
        for entry in section["entries"]
        if entry["title"].startswith("WVS")
    )


def test_get_resume_via_server():
    store = ResumeStore()
    src = seed_bright(store)
    server = make_server(store)
    result = _call(server, "get_resume", {"resume_id": src.resume_id})
    assert result.is_error is False
    resume = result.structured_content
    assert resume["resume_id"] == src.resume_id
    assert resume["heading"]["name"] == "Bright Owusu"
    assert resume["heading"]["slots"][0]["kind"] == "phone"
    assert _wvs(resume)["link_url"] is None


def test_copy_resume_via_server():
    store = ResumeStore()
    src = seed_bright(store)
    server = make_server(store)
    result = _call(
        server,
        "copy_resume",
        {
            "resume_id": src.resume_id,
            "base_revision": src.revision,
            "request_id": "req-copy-mcp",
            "copy_name": "PANW intern",
        },
    )
    assert result.is_error is False
    copied = result.structured_content
    assert copied["role"] == "copy"
    assert copied["source_id"] == src.resume_id
    assert copied["name"] == "PANW intern"
    assert copied["heading"]["name"] == "Bright Owusu"
    assert _wvs(copied)["link_url"] is None


def test_get_resume_not_found_is_tool_error():
    store = ResumeStore()
    seed_bright(store)
    server = make_server(store)
    with pytest.raises(ToolError, match="resume not found"):
        _call(server, "get_resume", {"resume_id": "nope"})


def test_conflict_includes_current_revision():
    store = ResumeStore()
    src = seed_bright(store)
    server = make_server(store)
    with pytest.raises(ToolError, match="current_revision") as err:
        _call(
            server,
            "copy_resume",
            {
                "resume_id": src.resume_id,
                "base_revision": 99,
                "request_id": "req-x",
                "copy_name": "Nope",
            },
        )
    assert str(src.revision) in str(err.value)


def test_source_protected_is_tool_error():
    store = ResumeStore()
    src = seed_bright(store)
    job_id = next(s for s in src.sections if s.kind == "experience").entries[0].entry_id
    server = make_server(store)
    with pytest.raises(ToolError, match="source is protected; copy_resume first"):
        _call(
            server,
            "remove_entry",
            {
                "resume_id": src.resume_id,
                "base_revision": src.revision,
                "request_id": "req-rm",
                "entry_id": job_id,
            },
        )


def test_validation_is_tool_error():
    store = ResumeStore()
    src = seed_bright(store)
    server = make_server(store)
    with pytest.raises(ToolError, match="at least one reorder argument is required"):
        _call(
            server,
            "reorder_resume",
            {
                "resume_id": src.resume_id,
                "base_revision": src.revision,
                "request_id": "req-empty",
            },
        )
