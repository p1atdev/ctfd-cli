from __future__ import annotations

import json

import httpx
import respx
from ctfd.cli import EXIT_CONFIG, EXIT_OPERATION, app
from typer.testing import CliRunner

API = "https://ctf.example/api/v1"
runner = CliRunner()


def test_challenge_list_json(monkeypatch) -> None:
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/challenges").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": [{"id": 1, "name": "Welcome", "value": 100}],
                },
            )
        )
        result = runner.invoke(app, ["challenges", "list", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["name"] == "Welcome"


def test_incorrect_submission_returns_operation_exit_code(monkeypatch) -> None:
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.post(f"{API}/challenges/attempt").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {"status": "incorrect", "message": "Incorrect"},
                },
            )
        )
        result = runner.invoke(app, ["challenges", "submit", "1", "flag{wrong}", "--json"])

    assert result.exit_code == EXIT_OPERATION
    assert json.loads(result.stdout)["status"] == "incorrect"


def test_missing_config_has_dedicated_exit_code(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CTFD_URL", raising=False)
    monkeypatch.delenv("CTFD_TOKEN", raising=False)

    result = runner.invoke(app, ["challenges", "list"])

    assert result.exit_code == EXIT_CONFIG
    assert "Error:" in result.stderr


def test_pull_creates_problem_markdown_and_downloads_files(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/challenges").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": [
                        {
                            "id": 1,
                            "type": "standard",
                            "name": "The first problem",
                            "category": "briefing",
                            "value": 100,
                        }
                    ],
                },
            )
        )
        router.get(f"{API}/challenges/1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": 1,
                        "type": "standard",
                        "name": "The first problem",
                        "category": "briefing",
                        "value": 100,
                        "description": "Read this first.",
                        "files": ["/files/task.txt?token=signed"],
                        "hints": [{"id": 2, "cost": 0, "content": "Look closely."}],
                    },
                },
            )
        )
        file_route = router.get("https://ctf.example/files/task.txt?token=signed").mock(
            return_value=httpx.Response(200, content=b"task data")
        )
        result = runner.invoke(app, ["pull"])

    challenge_dir = tmp_path / "challenges" / "briefing" / "01_The_first_problem"
    problem = challenge_dir / "problem.md"
    assert result.exit_code == 0
    assert problem.read_text(encoding="utf-8") == (
        "# The first problem\n"
        "\n"
        "- ID: 1\n"
        "- Category: briefing\n"
        "- Points: 100\n"
        "- Solves: -\n"
        "- Solved by me: no\n"
        "\n"
        "## Description\n"
        "\n"
        "Read this first.\n"
        "\n"
        "## Files\n"
        "\n"
        "- [task.txt](https://ctf.example/files/task.txt?token=signed)\n"
        "\n"
        "## Hints\n"
        "\n"
        "- Hint 2 (free): Look closely.\n"
    )
    assert (challenge_dir / "task.txt").read_bytes() == b"task data"
    assert file_route.calls.last.request.headers["Authorization"] == "Token token"


def test_pull_does_not_overwrite_existing_problem_or_files(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    challenge_dir = tmp_path / "challenges" / "briefing" / "01_The_first_problem"
    challenge_dir.mkdir(parents=True)
    problem = challenge_dir / "problem.md"
    attachment = challenge_dir / "task.txt"
    problem.write_text("existing problem\n", encoding="utf-8")
    attachment.write_bytes(b"existing data")

    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/challenges").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": [
                        {
                            "id": 1,
                            "name": "The first problem",
                            "category": "briefing",
                            "value": 100,
                        }
                    ],
                },
            )
        )
        router.get(f"{API}/challenges/1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "The first problem",
                        "category": "briefing",
                        "value": 100,
                        "description": "new problem",
                        "files": ["/files/task.txt"],
                    },
                },
            )
        )
        result = runner.invoke(app, ["pull"])

    assert result.exit_code == 0
    assert problem.read_text(encoding="utf-8") == "existing problem\n"
    assert attachment.read_bytes() == b"existing data"
    assert "1 skipped" in result.stdout


def test_token_is_not_printed_on_authentication_error(monkeypatch) -> None:
    token = "top-secret-token"
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", token)
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(
                401,
                json={"success": False, "errors": {"": ["Invalid token"]}},
            )
        )
        result = runner.invoke(app, ["me"])

    assert result.exit_code != 0
    assert token not in result.stdout
    assert token not in result.stderr


def test_me_omits_email_from_human_output_by_default(monkeypatch) -> None:
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "alice",
                        "email": "alice@example.com",
                    },
                },
            )
        )
        result = runner.invoke(app, ["me"])

    assert result.exit_code == 0
    assert "alice" in result.stdout
    assert "alice@example.com" not in result.stdout
    assert "Email" not in result.stdout


def test_me_show_email_includes_email_in_human_output(monkeypatch) -> None:
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "alice",
                        "email": "alice@example.com",
                    },
                },
            )
        )
        result = runner.invoke(app, ["me", "--show-email"])

    assert result.exit_code == 0
    assert "alice@example.com" in result.stdout
    assert "Email" in result.stdout


def test_me_omits_email_from_json_by_default(monkeypatch) -> None:
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "alice",
                        "email": "alice@example.com",
                    },
                },
            )
        )
        result = runner.invoke(app, ["me", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["name"] == "alice"
    assert "email" not in json.loads(result.stdout)


def test_me_show_email_includes_email_in_json(monkeypatch) -> None:
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "alice",
                        "email": "alice@example.com",
                    },
                },
            )
        )
        result = runner.invoke(app, ["me", "--json", "--show-email"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["email"] == "alice@example.com"


def test_short_challenge_list_outputs_one_plain_text_line_per_challenge(monkeypatch) -> None:
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/challenges").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": [
                        {
                            "id": 1,
                            "type": "standard",
                            "name": "Welcome",
                            "value": 100,
                            "category": "misc",
                            "solves": 5,
                            "solved_by_me": False,
                            "template": "/plugins/challenges/assets/view.html",
                            "script": "/plugins/challenges/assets/view.js",
                        }
                    ],
                },
            )
        )
        result = runner.invoke(app, ["--short", "challenges", "list"])

    assert result.exit_code == 0
    assert result.stdout.count("\n") == 2
    assert result.stdout == (
        "ID | NAME | CATEGORY | POINTS | SOLVES | STATUS\n"
        "1 | Welcome | misc | 100 | 5 | unsolved\n"
    )
    assert '"' not in result.stdout
    assert "{" not in result.stdout
    assert "[" not in result.stdout
    assert "template" not in result.stdout


def test_short_challenge_detail_is_readable_plain_text(monkeypatch) -> None:
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/challenges/1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": 1,
                        "type": "standard",
                        "name": "Welcome",
                        "value": 100,
                        "description": "Read the prompt.",
                        "files": ["/files/task.txt"],
                        "hints": [{"id": 2, "cost": 0, "content": "Look closely."}],
                        "view": "<section>large rendered HTML</section>",
                        "template": "/view.html",
                        "script": "/view.js",
                    },
                },
            )
        )
        result = runner.invoke(app, ["--short", "challenges", "show", "1"])

    assert result.exit_code == 0
    assert result.stdout == (
        "ID | NAME | CATEGORY | POINTS | SOLVES | STATUS\n"
        "1 | Welcome | - | 100 | - | unsolved\n"
        "description: Read the prompt.\n"
        "file: https://ctf.example/files/task.txt\n"
        "hint 2 | free | Look closely.\n"
    )
    assert '"' not in result.stdout
    assert "<section>" not in result.stdout
    assert "/view.html" not in result.stdout
    assert "/view.js" not in result.stdout


def test_short_me_outputs_only_name_score_and_place(monkeypatch) -> None:
    monkeypatch.setenv("CTFD_URL", "https://ctf.example")
    monkeypatch.setenv("CTFD_TOKEN", "token")
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "alice",
                        "email": "alice@example.com",
                        "score": 300,
                        "place": "2nd",
                        "country": None,
                        "fields": [],
                    },
                },
            )
        )
        result = runner.invoke(app, ["--short", "me"])

    assert result.exit_code == 0
    assert result.stdout == "NAME | SCORE | PLACE\nalice | 300 | 2nd\n"
    assert "alice@example.com" not in result.stdout
    assert '"' not in result.stdout
