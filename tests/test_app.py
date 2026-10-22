from starlette.testclient import TestClient

from myoverl_mcp.app import create_app
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.store import ResumeStore


def _client(tmp_path):
    store = ResumeStore(tmp_path)
    seed_bright(store)
    return TestClient(create_app(store)), store


def test_homepage_and_people(tmp_path):
    client, _store = _client(tmp_path)
    home = client.get("/")
    assert home.status_code == 200
    assert b"underleaf" in home.content.lower()
    assert b'type="module"' in home.content
    font = client.get("/fonts/lmroman10-regular.otf")
    assert font.status_code == 200
    js = client.get("/app.js").text
    assert "pdf-view.mjs" in js
    view = client.get("/pdf-view.mjs").text
    assert "convertToViewportPoint" in view
    assert "convertToViewportRectangle" not in view
    vendor = client.get("/vendor/pdfjs/pdf.mjs")
    assert vendor.status_code == 200
    people = client.get("/api/people").json()
    assert [p["name"] for p in people] == ["Bright"]


def test_copy_and_switch_person(tmp_path):
    client, store = _client(tmp_path)
    source_id = client.get("/api/people").json()[0]["source_id"]
    copied = client.post(
        f"/api/resumes/{source_id}/copy",
        json={"copy_name": "PANW intern"},
    ).json()
    assert copied["role"] == "copy"
    assert copied["name"] == "PANW intern"
    rows = client.get("/api/resumes?person=Bright").json()
    assert {r["name"] for r in rows} == {"Bright", "PANW intern"}

    beth = client.post(
        "/api/people",
        json={"person_name": "Beth", "heading_name": "Beth Example"},
    ).json()
    assert beth["role"] == "source"
    assert beth["heading"]["name"] == "Beth Example"
    people = client.get("/api/people").json()
    assert {p["name"] for p in people} == {"Bright", "Beth"}
    beth_rows = client.get("/api/resumes?person=Beth").json()
    assert [r["resume_id"] for r in beth_rows] == [beth["resume_id"]]


def test_update_bullet_via_api(tmp_path):
    client, _store = _client(tmp_path)
    source_id = client.get("/api/people").json()[0]["source_id"]
    resume = client.get(f"/api/resumes/{source_id}").json()
    job = next(s for s in resume["sections"] if s["kind"] == "experience")
    bullet = job["entries"][0]["bullets"][0]
    updated = client.post(
        f"/api/resumes/{source_id}/update",
        json={
            "base_revision": resume["revision"],
            "bullets": [{"bullet_id": bullet["bullet_id"], "text": "Edited on the paper."}],
        },
    ).json()
    new_job = next(s for s in updated["sections"] if s["kind"] == "experience")
    assert new_job["entries"][0]["bullets"][0]["text"] == "Edited on the paper."


def test_authentication_enforced_when_api_key_configured(tmp_path):
    store = ResumeStore(tmp_path)
    seed_bright(store)
    app = create_app(store, api_key="secret-key-123")
    client = TestClient(app)

    # Public static pages load without auth
    assert client.get("/").status_code == 200
    assert client.get("/app.js").status_code == 200

    # API endpoints require auth
    unauth = client.get("/api/people")
    assert unauth.status_code == 401
    assert "unauthorized" in unauth.json()["error"].lower()

    # Wrong key rejected
    bad = client.get("/api/people", headers={"Authorization": "Bearer wrong-key"})
    assert bad.status_code == 401

    # Bearer header succeeds
    bearer = client.get("/api/people", headers={"Authorization": "Bearer secret-key-123"})
    assert bearer.status_code == 200

    # x-api-key header succeeds
    xkey = client.get("/api/people", headers={"x-api-key": "secret-key-123"})
    assert xkey.status_code == 200

    # Query param token succeeds
    qparam = client.get("/api/people?token=secret-key-123")
    assert qparam.status_code == 200


def test_public_tunnel_host_header_does_not_return_421(tmp_path):
    store = ResumeStore(tmp_path)
    seed_bright(store)
    app = create_app(store)
    with TestClient(app) as client:
        # FastMCP streamable http endpoint under external tunnel host must not return 421 Misdirected Request
        response = client.get("/mcp", headers={"Host": "underleaf-app.trycloudflare.com"})
        assert response.status_code != 421
