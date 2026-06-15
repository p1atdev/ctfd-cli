from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ctfd.errors import CtfdConfigError


class CtfdSettings(BaseSettings):
    """Settings loaded from explicit values, the environment, and then .env."""

    model_config = SettingsConfigDict(
        env_prefix="CTFD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str
    token: SecretStr
    timeout: float = Field(default=10.0, gt=0)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be an absolute HTTP or HTTPS URL")
        if parsed.query or parsed.fragment:
            raise ValueError("must not contain a query string or fragment")
        return value.rstrip("/")

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must not be empty")
        return value


def load_settings(
    *,
    url: str | None = None,
    token: str | SecretStr | None = None,
    timeout: float | None = None,
    **settings_kwargs: Any,
) -> CtfdSettings:
    """Load settings while preserving BaseSettings source precedence."""

    values: dict[str, Any] = dict(settings_kwargs)
    if url is not None:
        values["url"] = url
    if token is not None:
        values["token"] = token
    if timeout is not None:
        values["timeout"] = timeout

    try:
        return CtfdSettings(**values)
    except ValidationError as exc:
        messages = []
        for error in exc.errors(include_url=False):
            location = ".".join(str(part) for part in error["loc"])
            messages.append(f"{location}: {error['msg']}")
        raise CtfdConfigError("; ".join(messages)) from None
