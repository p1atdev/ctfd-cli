from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from ctfd.errors import (
    CtfdAPIError,
    CtfdAuthenticationError,
    CtfdConnectionError,
    CtfdNotFoundError,
    CtfdPermissionError,
    CtfdRateLimitError,
    CtfdResponseError,
    CtfdTimeoutError,
)
from ctfd.models import (
    AttemptResult,
    ChallengeDetail,
    ChallengeSummary,
    Hint,
    ScoreboardEntry,
    Submission,
    Unlock,
    User,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _normalize_urls(url: str) -> tuple[str, str]:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute HTTP or HTTPS URL")

    path = parsed.path.rstrip("/")
    site_path = path[: -len("/api/v1")] if path.endswith("/api/v1") else path
    site_url = urlunsplit((parsed.scheme, parsed.netloc, site_path, "", "")).rstrip("/")
    api_url = f"{site_url}/api/v1"
    return site_url, api_url


def _format_errors(errors: Any) -> str:
    if isinstance(errors, Mapping):
        messages: list[str] = []
        for field, value in errors.items():
            text = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
            messages.append(f"{field}: {text}" if field else text)
        return "; ".join(messages)
    if isinstance(errors, list):
        return "; ".join(str(item) for item in errors)
    return str(errors) if errors else "CTFd API request failed"


class CtfdClient:
    """Synchronous client for participant-facing CTFd API v1 endpoints."""

    def __init__(
        self,
        url: str,
        token: str | SecretStr,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.site_url, self.api_url = _normalize_urls(url)
        token_value = token.get_secret_value() if isinstance(token, SecretStr) else token
        if not token_value:
            raise ValueError("token must not be empty")
        self._http = httpx.Client(
            base_url=f"{self.api_url}/",
            headers={
                "Authorization": f"Token {token_value}",
                "Accept": "application/json",
                "User-Agent": "ctfd-cli/0.1.0",
            },
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> CtfdClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def list_challenges(
        self,
        *,
        name: str | None = None,
        category: str | None = None,
        challenge_type: str | None = None,
        state: str | None = None,
        query: str | None = None,
        field: str | None = None,
    ) -> list[ChallengeSummary]:
        params = {
            "name": name,
            "category": category,
            "type": challenge_type,
            "state": state,
            "q": query,
            "field": field,
        }
        data = self._request("GET", "challenges", params=params)
        return self._parse_list(ChallengeSummary, data)

    def get_challenge(self, challenge_id: int) -> ChallengeDetail:
        data = self._request("GET", f"challenges/{challenge_id}")
        challenge = self._parse_model(ChallengeDetail, data)
        challenge.files = [self.absolute_url(file_url) for file_url in challenge.files]
        return challenge

    def submit_challenge(self, challenge_id: int, submission: str) -> AttemptResult:
        data = self._request(
            "POST",
            "challenges/attempt",
            json={"challenge_id": challenge_id, "submission": submission},
        )
        return self._parse_model(AttemptResult, data)

    def get_hint(self, hint_id: int) -> Hint:
        data = self._request("GET", f"hints/{hint_id}")
        return self._parse_model(Hint, data)

    def unlock_hint(self, hint_id: int) -> Hint:
        data = self._request(
            "POST",
            "unlocks",
            json={"target": hint_id, "type": "hints"},
        )
        self._parse_model(Unlock, data)
        return self.get_hint(hint_id)

    def get_scoreboard(self) -> list[ScoreboardEntry]:
        data = self._request("GET", "scoreboard")
        entries = self._parse_list(ScoreboardEntry, data)
        for entry in entries:
            if entry.account_url:
                entry.account_url = self.absolute_url(entry.account_url)
        return entries

    def get_me(self) -> User:
        data = self._request("GET", "users/me")
        return self._parse_model(User, data)

    def get_my_solves(self) -> list[Submission]:
        data = self._request("GET", "users/me/solves")
        return self._parse_list(Submission, data)

    def get_my_submissions(self, *, challenge_id: int | None = None) -> list[Submission]:
        data = self._request(
            "GET",
            "users/me/submissions",
            params={"challenge_id": challenge_id},
        )
        return self._parse_list(Submission, data)

    def absolute_url(self, value: str) -> str:
        return urljoin(f"{self.site_url}/", value)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        filtered_params = (
            {key: value for key, value in params.items() if value is not None}
            if params
            else None
        )
        try:
            response = self._http.request(method, path, params=filtered_params, json=json)
        except httpx.TimeoutException as exc:
            raise CtfdTimeoutError("request to CTFd timed out") from exc
        except httpx.RequestError as exc:
            raise CtfdConnectionError("could not connect to the CTFd server") from exc

        try:
            payload = response.json()
        except ValueError:
            if response.is_error:
                self._raise_api_error(
                    f"CTFd returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    errors=None,
                    retry_after=response.headers.get("Retry-After"),
                )
            raise CtfdResponseError("CTFd returned a non-JSON response") from None

        if not isinstance(payload, dict) or "success" not in payload:
            if response.is_error:
                errors = payload.get("errors") if isinstance(payload, dict) else None
                if not errors and isinstance(payload, dict):
                    errors = payload.get("message")
                message = (
                    _format_errors(errors)
                    if errors
                    else f"CTFd returned HTTP {response.status_code}"
                )
                self._raise_api_error(
                    message,
                    status_code=response.status_code,
                    errors=errors,
                    retry_after=response.headers.get("Retry-After"),
                )
            raise CtfdResponseError("CTFd returned an invalid API response")

        if payload["success"] is True:
            if "data" not in payload:
                return None
            return payload["data"]

        errors = payload.get("errors")
        message = _format_errors(errors)
        self._raise_api_error(
            message,
            status_code=response.status_code,
            errors=errors,
            retry_after=response.headers.get("Retry-After"),
        )
        raise AssertionError("unreachable")

    @staticmethod
    def _raise_api_error(
        message: str,
        *,
        status_code: int,
        errors: Any,
        retry_after: str | None,
    ) -> None:
        kwargs = {"status_code": status_code, "errors": errors}
        if status_code == 401:
            raise CtfdAuthenticationError(message, **kwargs)
        if status_code == 403:
            raise CtfdPermissionError(message, **kwargs)
        if status_code == 404:
            raise CtfdNotFoundError(message, **kwargs)
        if status_code == 429:
            raise CtfdRateLimitError(message, retry_after=retry_after, **kwargs)
        raise CtfdAPIError(message, **kwargs)

    @staticmethod
    def _parse_model(model: type[ModelT], data: Any) -> ModelT:
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise CtfdResponseError(f"invalid {model.__name__} response: {exc}") from None

    @classmethod
    def _parse_list(cls, model: type[ModelT], data: Any) -> list[ModelT]:
        if not isinstance(data, list):
            raise CtfdResponseError(f"invalid {model.__name__} list response")
        return [cls._parse_model(model, item) for item in data]
