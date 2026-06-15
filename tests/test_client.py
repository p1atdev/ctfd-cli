from __future__ import annotations

import httpx
import pytest
import respx

from ctfd import CtfdClient
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

API = "https://ctf.example/api/v1"


def test_list_challenges_sends_auth_and_filters() -> None:
    with respx.mock(assert_all_called=True) as router:
        route = router.get(f"{API}/challenges").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": [
                        {
                            "id": 1,
                            "name": "Welcome",
                            "category": "misc",
                            "value": 100,
                            "solves": 3,
                            "plugin_field": "kept",
                        }
                    ],
                },
            )
        )
        with CtfdClient("https://ctf.example/", "secret-token") as client:
            challenges = client.list_challenges(category="misc", query="Wel", field="name")

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Token secret-token"
    assert request.headers["Content-Type"] == "application/json"
    assert dict(request.url.params) == {"category": "misc", "q": "Wel", "field": "name"}
    assert challenges[0].name == "Welcome"
    assert challenges[0].model_extra == {"plugin_field": "kept"}


def test_api_v1_url_is_not_duplicated() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {"id": 7, "name": "alice", "place": "17th"},
                },
            )
        )
        with CtfdClient(f"{API}/", "token") as client:
            user = client.get_me()

    assert user.name == "alice"
    assert user.place == "17th"


def test_get_challenge_normalizes_file_urls_and_preserves_fields() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/challenges/3").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "id": 3,
                        "name": "Forensics",
                        "value": 200,
                        "description": "Inspect it",
                        "files": ["/files/example.bin?token=signed"],
                        "hints": [{"id": 9, "cost": 10}],
                        "plugin": {"dynamic": True},
                    },
                },
            )
        )
        with CtfdClient("https://ctf.example", "token") as client:
            challenge = client.get_challenge(3)

    assert challenge.files == ["https://ctf.example/files/example.bin?token=signed"]
    assert challenge.hints[0].id == 9
    assert challenge.model_extra == {"plugin": {"dynamic": True}}


def test_submit_returns_business_result_even_with_403_status() -> None:
    with respx.mock(assert_all_called=True) as router:
        route = router.post(f"{API}/challenges/attempt").mock(
            return_value=httpx.Response(
                403,
                json={
                    "success": True,
                    "data": {"status": "authentication_required", "message": "Log in"},
                },
            )
        )
        with CtfdClient("https://ctf.example", "token") as client:
            result = client.submit_challenge(4, "flag{test}")

    assert route.calls.last.request.content == b'{"challenge_id":4,"submission":"flag{test}"}'
    assert result.status == "authentication_required"


def test_unlock_hint_posts_unlock_then_fetches_content() -> None:
    with respx.mock(assert_all_called=True) as router:
        unlock = router.post(f"{API}/unlocks").mock(
            return_value=httpx.Response(
                201,
                json={
                    "success": True,
                    "data": {"id": 8, "target": 5, "type": "hints"},
                },
            )
        )
        router.get(f"{API}/hints/5").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {"id": 5, "cost": 20, "content": "Try strings."},
                },
            )
        )
        with CtfdClient("https://ctf.example", "token") as client:
            hint = client.unlock_hint(5)

    assert unlock.calls.last.request.content == b'{"target":5,"type":"hints"}'
    assert hint.content == "Try strings."


def test_scoreboard_normalizes_account_url() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/scoreboard").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": [
                        {
                            "pos": 1,
                            "account_id": 2,
                            "account_url": "/users/2",
                            "name": "alice",
                            "score": 300,
                        }
                    ],
                },
            )
        )
        with CtfdClient("https://ctf.example", "token") as client:
            entries = client.get_scoreboard()

    assert entries[0].account_url == "https://ctf.example/users/2"


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, CtfdAuthenticationError),
        (403, CtfdPermissionError),
        (404, CtfdNotFoundError),
        (429, CtfdRateLimitError),
        (500, CtfdAPIError),
    ],
)
def test_structured_api_errors(status: int, exception: type[Exception]) -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(
                status,
                headers={"Retry-After": "30"},
                json={"success": False, "errors": {"": ["Request failed"]}},
            )
        )
        with (
            CtfdClient("https://ctf.example", "token") as client,
            pytest.raises(exception) as caught,
        ):
            client.get_me()

    if status == 429:
        assert isinstance(caught.value, CtfdRateLimitError)
        assert caught.value.retry_after == "30"


def test_non_json_success_is_response_error() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(200, text="<html>login</html>")
        )
        with (
            CtfdClient("https://ctf.example", "token") as client,
            pytest.raises(CtfdResponseError),
        ):
            client.get_me()


def test_flask_restx_error_is_mapped_by_status() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me/submissions").mock(
            return_value=httpx.Response(403, json={"message": "Forbidden"})
        )
        with (
            CtfdClient("https://ctf.example", "token") as client,
            pytest.raises(CtfdPermissionError, match="Forbidden"),
        ):
            client.get_my_submissions()


def test_non_json_http_error_is_mapped_by_status() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        with (
            CtfdClient("https://ctf.example", "token") as client,
            pytest.raises(CtfdAuthenticationError),
        ):
            client.get_me()


def test_invalid_model_is_response_error() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get(f"{API}/users/me").mock(
            return_value=httpx.Response(
                200,
                json={"success": True, "data": {"name": "missing id"}},
            )
        )
        with (
            CtfdClient("https://ctf.example", "token") as client,
            pytest.raises(CtfdResponseError),
        ):
            client.get_me()


def test_connection_error_is_wrapped() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("failed", request=request)

    with (
        CtfdClient(
            "https://ctf.example",
            "token",
            transport=httpx.MockTransport(fail),
        ) as client,
        pytest.raises(CtfdConnectionError),
    ):
        client.get_me()


def test_timeout_is_wrapped() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with (
        CtfdClient(
            "https://ctf.example",
            "token",
            transport=httpx.MockTransport(fail),
        ) as client,
        pytest.raises(CtfdTimeoutError),
    ):
        client.get_me()
