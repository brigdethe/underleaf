from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from myoverl_mcp import tools as tool_fns
from myoverl_mcp.errors import (
    ConflictError,
    NotFoundError,
    SourceProtectedError,
    ValidationError as DomainValidationError,
)
from myoverl_mcp.instructions import INSTRUCTIONS, tailor
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.fastmcp.exceptions import ToolError
    from mcp.server.fastmcp.prompts.base import Prompt
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer as FastMCP
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.server.mcpserver.prompts.base import Prompt

TOOL_NAMES = (
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
)


def _map_error(exc: BaseException) -> ToolError:
    if isinstance(exc, NotFoundError):
        return ToolError("resume not found")
    if isinstance(exc, ConflictError):
        return ToolError(f"revision conflict: current_revision={exc.current_revision}")
    if isinstance(exc, SourceProtectedError):
        return ToolError("source is protected; copy_resume first")
    if isinstance(exc, DomainValidationError):
        return ToolError(str(exc))
    raise exc


def _bind(fn: Callable[..., Any], store: ResumeStore) -> Callable[..., Any]:
    signature = inspect.signature(fn)
    parameters = [parameter for name, parameter in signature.parameters.items() if name != "store"]
    bound_signature = signature.replace(parameters=parameters)
    annotations = {name: value for name, value in getattr(fn, "__annotations__", {}).items() if name != "store"}

    def tool(**kwargs: Any) -> Any:
        try:
            return fn(store, **kwargs)
        except (NotFoundError, ConflictError, SourceProtectedError, DomainValidationError) as exc:
            raise _map_error(exc) from None

    tool.__name__ = fn.__name__
    tool.__doc__ = fn.__doc__ or fn.__name__.replace("_", " ")
    tool.__signature__ = bound_signature
    tool.__annotations__ = annotations
    return tool


def make_server(store: ResumeStore) -> FastMCP:
    server = FastMCP("underleaf", instructions=INSTRUCTIONS)
    for name in TOOL_NAMES:
        server.add_tool(_bind(getattr(tool_fns, name), store), name=name)
    server.add_prompt(Prompt.from_function(tailor, name="tailor"))
    return server


def main() -> None:
    from myoverl_mcp.app import main as app_main

    app_main()


if __name__ == "__main__":
    main()
