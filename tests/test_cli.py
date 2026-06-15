from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from ctfd.cli import EXIT_CONFIG, EXIT_OPERATION, app

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
