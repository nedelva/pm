import httpx
import pytest

from app.openrouter import OPENROUTER_URL, OpenRouterClient, OpenRouterError


def client_for(handler) -> OpenRouterClient:
    return OpenRouterClient(api_key="test-key", model="test/model:free", transport=httpx.MockTransport(handler))


def test_complete_returns_message_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(OPENROUTER_URL)
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.read()
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "4"}}]},
            request=request,
        )

    client = client_for(handler)

    assert client.complete("What is 2 + 2?") == "4"


def test_missing_api_key_is_rejected() -> None:
    client = OpenRouterClient(api_key="", transport=httpx.MockTransport(lambda _: httpx.Response(200)))

    with pytest.raises(OpenRouterError, match="not configured"):
        client.complete("What is 2 + 2?")


@pytest.mark.parametrize("status_code", [401, 500])
def test_provider_errors_are_redacted(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="provider secret", request=request)

    with pytest.raises(OpenRouterError, match="provider returned an error"):
        client_for(handler).complete("test")


def test_rate_limit_has_specific_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    with pytest.raises(OpenRouterError, match="rate-limited"):
        client_for(handler).complete("test")


def test_timeout_has_actionable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(OpenRouterError, match="timed out"):
        client_for(handler).complete("test")


def test_malformed_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []}, request=request)

    with pytest.raises(OpenRouterError, match="invalid response"):
        client_for(handler).complete("test")


def test_connectivity_check_returns_model_and_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "4"}}]},
            request=request,
        )

    assert client_for(handler).connectivity_check() == {
        "model": "test/model:free",
        "answer": "4",
    }


def test_complete_structured_requests_json_schema_and_decodes_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode()
        assert '"response_format"' in payload
        assert '"reasoning":{"enabled":false}' in payload.replace(" ", "")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"message":"Done","operations":[]}'}}]},
            request=request,
        )

    result = client_for(handler).complete_structured(
        [{"role": "user", "content": "Create a card."}],
        {"type": "object"},
    )

    assert result == {"message": "Done", "operations": []}


def test_complete_structured_extracts_json_from_explanatory_markdown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": 'Here is the result:\n```json\n{"message":"Done","operations":[]}\n```'
                        }
                    }
                ]
            },
            request=request,
        )

    assert client_for(handler).complete_structured([], {}) == {
        "message": "Done",
        "operations": [],
    }


def test_complete_structured_falls_back_when_schema_format_is_rejected() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(400, request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"message":"Done","operations":[]}'}}]},
            request=request,
        )

    assert client_for(handler).complete_structured([], {}) == {
        "message": "Done",
        "operations": [],
    }
    assert calls == 2