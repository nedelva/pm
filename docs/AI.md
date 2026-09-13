# AI Connectivity

Phase 8 uses OpenRouter through a backend-only client. The browser never receives the API key.

## Configuration

- `OPENROUTER_API_KEY`: required for live requests.
- `OPENROUTER_MODEL`: optional model override.
- Default model selected from the OpenRouter free catalog on 2026-09-13: `nvidia/nemotron-3.5-lightning:free`.

Free-model availability can change, so the model remains configurable. The selected model is text-capable and is used for both the Phase 8 connectivity check and the Phase 9 structured chat contract.

## Connectivity Check

After authentication, the backend endpoint `POST /api/ai/connectivity` sends a backend-only prompt asking the model to answer `2 + 2`. A successful response contains the configured model ID and provider answer.

Automated tests use mocked HTTP transport and do not require a key. The client uses a 30-second timeout and returns safe errors for missing configuration, network failures, timeouts, rate limits, provider errors, and malformed responses. Provider response bodies and credentials are not returned in errors.

## Structured Chat Contract

`POST /api/ai/chat` requires an authenticated session and accepts a question plus up to 20 browser-held messages. The backend always sends the authenticated user's current board JSON, the question, and that history to OpenRouter.

The provider must return JSON with an assistant `message` and zero or more validated `create_card`, `edit_card`, or `move_card` operations. Delete operations are not supported. IDs and column IDs must exist on the authenticated user's board, and all operations in one response are applied atomically. If the selected free model rejects OpenRouter's JSON Schema transport, the backend retries once with an explicit JSON-only instruction and still applies the same strict validation afterward.

The endpoint returns the assistant message, accepted operations, and the refreshed board. Invalid structured output, unknown IDs, unsupported operations, and provider failures do not modify the database.
