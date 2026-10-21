import pytest

from myoverl_mcp.ids import new_id
from myoverl_mcp.models import Heading, Resume
from myoverl_mcp.store import ResumeStore


def make_source(name: str = "Bright") -> Resume:
    return Resume(
        resume_id=new_id("res"),
        name=name,
        role="source",
        heading=Heading(name=f"{name} Owusu"),
        editor_url="https://example.invalid/r/pending",
    )


@pytest.fixture
def store():
    return ResumeStore()
