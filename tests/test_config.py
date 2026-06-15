from __future__ import annotations

import pytest

from ctfd.config import load_settings
from ctfd.errors import CtfdConfigError


def test_explicit_values_override_environment_and_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CTFD_URL=https://dotenv.example\nCTFD_TOKEN=dotenv-token\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CTFD_URL", "https://environment.example")
    monkeypatch.setenv("CTFD_TOKEN", "environment-token")

    settings = load_settings(
        url="https://explicit.example/",
        token="explicit-token",
        _env_file=env_file,
    )

    assert settings.url == "https://explicit.example"
    assert settings.token.get_secret_value() == "explicit-token"


def test_environment_overrides_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CTFD_URL=https://dotenv.example\nCTFD_TOKEN=dotenv-token\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CTFD_URL", "https://environment.example")
    monkeypatch.setenv("CTFD_TOKEN", "environment-token")

    settings = load_settings(_env_file=env_file)

    assert settings.url == "https://environment.example"
    assert settings.token.get_secret_value() == "environment-token"


def test_missing_settings_raise_safe_config_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("CTFD_URL", raising=False)
    monkeypatch.delenv("CTFD_TOKEN", raising=False)

    with pytest.raises(CtfdConfigError) as caught:
        load_settings(_env_file=tmp_path / "missing.env")

    message = str(caught.value)
    assert "url" in message
    assert "token" in message


@pytest.mark.parametrize("url", ["ctf.example", "ftp://ctf.example", "https://ctf.example?q=1"])
def test_invalid_url_raises_config_error(url: str) -> None:
    with pytest.raises(CtfdConfigError):
        load_settings(url=url, token="token", _env_file=None)


def test_empty_token_raises_config_error() -> None:
    with pytest.raises(CtfdConfigError):
        load_settings(url="https://ctf.example", token="", _env_file=None)
