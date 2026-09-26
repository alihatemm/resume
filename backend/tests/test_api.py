import sqlite3

from app import config

from .conftest import FAKE_GOOGLE_KEY, commit_all, git


def make_changes(repo):
    (repo / "main.py").write_text("def get_user(headers):\n    return headers.get('authorization')\n")
    (repo / "middleware.py").write_text("def strip_headers(req):\n    return req\n")


def test_full_checkpoint_lifecycle(client, repo):
    make_changes(repo)
    payload = {
        "repo_path": str(repo),
        "note": "Debugging empty auth headers.\nCheck the middleware order next.",
        "terminal_text": f"GEMINI_API_KEY={FAKE_GOOGLE_KEY}\nKeyError: 'authorization'\n",
        "transcript": "I think the middleware strips headers before main.py.",
        "links": ["https://fastapi.tiangolo.com/tutorial/middleware/", "javascript:alert(1)"],
    }

    # create
    res = client.post("/api/checkpoints", json=payload)
    assert res.status_code == 201, res.text
    cp = res.json()
    assert cp["status"] == "ai_failed"  # AI disabled in tests -> placeholder summary
    assert cp["repo_path"] == str(repo.resolve())
    assert cp["git"]["branch"] == "main"
    assert {f["path"] for f in cp["git"]["changed_files"]} == {"main.py", "middleware.py"}
    s = cp["summary"]
    assert s["title"] == "Debugging empty auth headers."
    assert s["next_step"] == "Check the middleware order next."
    assert s["problem"] == payload["transcript"]
    assert s["errors"][-1] == "KeyError: 'authorization'"
    assert [link["url"] for link in s["links"]] == ["https://fastapi.tiangolo.com/tutorial/middleware/"]
    assert s["files"][0]["line"] is None and s["files"][0]["abs_path"] is None

    # secrets never returned...
    assert FAKE_GOOGLE_KEY not in res.text
    assert "GEMINI_API_KEY=[REDACTED]" in cp["terminal_text"]
    # ...and never persisted, in any column
    with sqlite3.connect(config.DB_PATH) as conn:
        rows = conn.execute("SELECT * FROM checkpoints").fetchall()
    assert FAKE_GOOGLE_KEY not in repr(rows)

    # list
    items = client.get("/api/checkpoints").json()
    assert len(items) == 1
    assert items[0]["id"] == cp["id"]
    assert items[0]["title"] == s["title"]
    assert items[0]["next_step"] == s["next_step"]
    assert "diff" not in items[0]

    # get
    assert client.get(f"/api/checkpoints/{cp['id']}").json() == cp

    # delete
    assert client.delete(f"/api/checkpoints/{cp['id']}").status_code == 204
    assert client.get(f"/api/checkpoints/{cp['id']}").status_code == 404
    assert client.delete(f"/api/checkpoints/{cp['id']}").status_code == 404
    assert client.get("/api/checkpoints").json() == []


def test_create_with_only_repo_path_uses_defaults(client, repo):
    make_changes(repo)
    cp = client.post("/api/checkpoints", json={"repo_path": str(repo)}).json()
    assert cp["summary"]["title"] == "Work on main"
    assert cp["summary"]["next_step"] == "Review your uncommitted changes."


def test_invalid_repo_returns_400_with_string_detail(client, tmp_path):
    res = client.post("/api/checkpoints", json={"repo_path": str(tmp_path)})
    assert res.status_code == 400
    assert "Not a git repository" in res.json()["detail"]


def test_validation_error_detail_is_a_string(client):
    res = client.post("/api/checkpoints", json={"note": "missing repo_path"})
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert isinstance(detail, str) and "repo_path" in detail


def test_missing_checkpoint_returns_404(client):
    res = client.get("/api/checkpoints/999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Checkpoint 999 not found."


def test_list_is_newest_first_and_filterable(client, repo, tmp_path):
    other = tmp_path / "other-repo"
    other.mkdir()
    git(other, "init", "-q", "-b", "dev")
    (other / "x.py").write_text("x = 1\n")
    commit_all(other, "init")

    first = client.post("/api/checkpoints", json={"repo_path": str(repo), "note": "first"}).json()
    second = client.post("/api/checkpoints", json={"repo_path": str(other), "note": "second"}).json()

    assert [i["id"] for i in client.get("/api/checkpoints").json()] == [second["id"], first["id"]]
    filtered = client.get("/api/checkpoints", params={"repo_path": first["repo_path"]}).json()
    assert [i["id"] for i in filtered] == [first["id"]]


def test_inspect_repo(client, repo):
    make_changes(repo)
    res = client.get("/api/repo/inspect", params={"path": str(repo)})
    assert res.status_code == 200
    assert res.json()["repo_name"] == "demo-api"
    assert client.get("/api/repo/inspect", params={"path": "nope"}).status_code == 400
