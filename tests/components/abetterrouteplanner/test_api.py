"""Tests for the A Better Routeplanner v1 API client.

The wire surface under test:

* ``POST https://api.iternio.com/1/session/get_tlm``
* Header ``Authorization: APIKEY <ABRP_APP_KEY>``
* Body ``{"session_id": "<oauth access_token>"}``
* Response envelope ``{"status": "ok"|"error", "result"|"error": ...}``

Auth-vs-generic error routing uses the regex heuristic
``/(?i)session|auth|token|invalid|expired/`` on the ``error`` text.
"""

from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.components.abetterrouteplanner.api import (
    AbrpApiError,
    AbrpAuthError,
    AbrpClient,
    AbrpTelemetryClient,
    AbrpVehicle,
    _parse_sse_event,
)
from homeassistant.components.abetterrouteplanner.const import (
    ABRP_API_V2_BASE,
    ABRP_APP_KEY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import (
    ABRP_GET_TLM_URL,
    MOCK_PAINT,
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_NAME,
    build_garage_response,
    build_vehicle_record,
)

from tests.test_util.aiohttp import AiohttpClientMocker

ACCESS_TOKEN = "mock-access-token"

# v2 one-shot telemetry endpoint — single-vehicle JSON poll used by the seed
# step. Path-scopes ``vehicleId`` (no body, no query), per the swagger.
ABRP_V2_TLM_ONE_SHOT_URL = f"{ABRP_API_V2_BASE}/tlm/{MOCK_VEHICLE_ID}"

# v2 catalog endpoint — full vehicle template list, fetched lazily-once by
# ``AbrpClient.async_get_catalog``. No query params, no body.
ABRP_V2_CATALOG_URL = f"{ABRP_API_V2_BASE}/vehicle/_list"


@pytest.fixture(name="client")
async def mock_client(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> AbrpClient:
    """Construct an ``AbrpClient`` bound to HA's shared aiohttp session.

    The dependency on ``aioclient_mock`` is load-bearing: it must be
    instantiated before ``async_get_clientsession`` is called so the
    ``async_create_clientsession`` patch is in effect when HA's session cache
    is populated for this ``hass``. Async because ``ClientSession``'s
    connector requires a running event loop.
    """
    return AbrpClient(async_get_clientsession(hass), ABRP_APP_KEY, ACCESS_TOKEN)


async def test_async_get_vehicles_single(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A one-vehicle garage parses into one ``AbrpVehicle`` with expected fields."""
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response())

    vehicles = await client.async_get_vehicles()

    assert len(vehicles) == 1
    vehicle = vehicles[0]
    assert isinstance(vehicle, AbrpVehicle)
    assert vehicle.vehicle_id == MOCK_VEHICLE_ID
    assert vehicle.name == MOCK_VEHICLE_NAME
    assert vehicle.vehicle_model == MOCK_VEHICLE_MODEL
    assert vehicle.paint == MOCK_PAINT


async def test_async_get_vehicles_empty(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An empty garage returns an empty list (not None, not an exception)."""
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response([]))

    vehicles = await client.async_get_vehicles()

    assert vehicles == []


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"status": "ok"}, id="missing_result_key"),
        pytest.param({"status": "ok", "result": "oops"}, id="result_is_str"),
        pytest.param({"status": "ok", "result": None}, id="result_is_null"),
        pytest.param({"status": "ok", "result": {"x": 1}}, id="result_is_dict"),
    ],
)
async def test_async_get_vehicles_malformed_success_envelope(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
    payload: dict[str, Any],
) -> None:
    """``status:ok`` with missing/non-list ``result`` surfaces as AbrpApiError.

    A bare ``payload["result"]`` would crash with KeyError or feed a
    non-iterable into the dataclass parser; the client must convert this to
    the public ``AbrpApiError`` boundary error instead.
    """
    aioclient_mock.post(ABRP_GET_TLM_URL, json=payload)

    with pytest.raises(AbrpApiError):
        await client.async_get_vehicles()


@pytest.mark.parametrize(
    "malformed_body",
    [
        pytest.param("<html><body>502 Bad Gateway</body></html>", id="html"),
        pytest.param("", id="empty"),
        pytest.param('{"result": ', id="truncated_json"),
    ],
)
async def test_async_get_vehicles_malformed_json_raises_api_error(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
    malformed_body: str,
) -> None:
    """Malformed JSON body from the v1 garage endpoint wraps as ``AbrpApiError``.

    Regression guard. Without the wrap, ``await response.json()`` raises a bare
    ``ValueError`` / ``JSONDecodeError`` which propagates uncaught out
    of :meth:`AbrpClient.async_get_vehicles` (the only ``except`` band
    is ``ClientError``, NOT ``ValueError``). The call is wrapped and
    surfaces as the public ``AbrpApiError`` boundary type with the
    original ``ValueError`` preserved on ``__cause__``.

    Three parametrized cases — each drives the same wrap path through a
    different ``ValueError``-subclass shape:

    * ``html`` — upstream emitted a 200 with a CDN error page (raw
      HTML); ``json.loads`` immediately raises ``JSONDecodeError`` on
      ``<``.
    * ``empty`` — network truncated the response after headers; empty
      body → ``JSONDecodeError`` on "Expecting value".
    * ``truncated_json`` — partial transfer; ``json.loads`` raises
      ``JSONDecodeError`` mid-parse.

    Pinning ``__cause__ is ValueError`` covers ``JSONDecodeError`` too
    (subclass of ``ValueError``) without coupling the test to the
    specific subclass the ``from err`` chain happens to capture.

    Mirrors the sibling-site guards already landed on
    :meth:`AbrpTelemetryClient.async_get_one_shot` and
    :meth:`AbrpClient.async_get_catalog`.
    """
    aioclient_mock.post(ABRP_GET_TLM_URL, status=200, text=malformed_body)

    with pytest.raises(AbrpApiError) as excinfo:
        await client.async_get_vehicles()

    assert isinstance(excinfo.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "response_kwargs",
    [
        pytest.param({"text": "null"}, id="null"),
        pytest.param({"json": []}, id="empty_list"),
        pytest.param(
            {"json": [build_vehicle_record(vehicle_id=1)]}, id="list_of_dicts"
        ),
        pytest.param({"json": "just a string"}, id="string"),
        pytest.param({"json": 42}, id="integer"),
    ],
)
async def test_async_get_vehicles_rejects_non_dict_payload(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
    response_kwargs: dict[str, Any],
) -> None:
    """A non-dict JSON body for the v1 garage endpoint raises ``AbrpApiError``.

    Mirrors the sibling adversarial set at
    ``test_async_get_one_shot_rejects_non_dict_payload``. Without the
    shape check, a JSON-valid non-dict (list, scalar, JSON-null) reaches
    ``payload.get("status")`` and raises ``AttributeError`` out-of-band of the
    ``(AbrpAuthError, AbrpApiError)`` boundary the coordinator catches —
    symmetric closure of the malformed-JSON failure class sealed for the
    same site.
    """
    aioclient_mock.post(ABRP_GET_TLM_URL, **response_kwargs)

    with pytest.raises(AbrpApiError):
        await client.async_get_vehicles()


async def test_async_get_vehicles_multi(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Multiple vehicles all parse; order is preserved."""
    records = [
        build_vehicle_record(vehicle_id=1, name="Vehicle A"),
        build_vehicle_record(vehicle_id=2, name="Vehicle B"),
        build_vehicle_record(vehicle_id=3, name="Vehicle C"),
    ]
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response(records))

    vehicles = await client.async_get_vehicles()

    assert [v.vehicle_id for v in vehicles] == [1, 2, 3]
    assert [v.name for v in vehicles] == ["Vehicle A", "Vehicle B", "Vehicle C"]


async def test_async_get_vehicles_request_shape(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Outgoing request: POST + APIKEY header + ``session_id`` body."""
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response())

    await client.async_get_vehicles()

    assert len(aioclient_mock.mock_calls) == 1
    method, url, data, headers = aioclient_mock.mock_calls[0]
    assert method.lower() == "post"
    assert str(url) == ABRP_GET_TLM_URL
    assert data == {"session_id": ACCESS_TOKEN}
    assert headers["Authorization"] == f"APIKEY {ABRP_APP_KEY}"


@pytest.mark.parametrize(
    "error_text",
    [
        pytest.param("invalid session", id="invalid_and_session"),
        pytest.param("Authentication failed", id="auth"),
        pytest.param("Token expired", id="token_and_expired"),
        pytest.param("session_id invalid", id="session_and_invalid"),
        pytest.param("auth_required", id="auth_required_underscore"),
        pytest.param("authorization failed", id="authorization"),
        pytest.param("invalid_credentials", id="invalid_credentials"),
    ],
)
async def test_status_error_with_auth_keywords_raises_auth_error(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
    error_text: str,
) -> None:
    """``status:error`` with auth-heuristic text → ``AbrpAuthError``."""
    aioclient_mock.post(
        ABRP_GET_TLM_URL,
        json={"status": "error", "error": error_text},
    )

    with pytest.raises(AbrpAuthError):
        await client.async_get_vehicles()


@pytest.mark.parametrize(
    "error_text",
    [
        pytest.param("Backend overloaded", id="backend"),
        pytest.param("Rate limit reached", id="rate_limit"),
        pytest.param("Internal failure", id="internal"),
        pytest.param("invalid vehicle_model", id="invalid_other_word"),
    ],
)
async def test_status_error_without_auth_keywords_raises_api_error(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
    error_text: str,
) -> None:
    """``status:error`` without auth-heuristic text → ``AbrpApiError``."""
    aioclient_mock.post(
        ABRP_GET_TLM_URL,
        json={"status": "error", "error": error_text},
    )

    with pytest.raises(AbrpApiError):
        await client.async_get_vehicles()


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"status": HTTPStatus.INTERNAL_SERVER_ERROR}, id="500"),
        pytest.param({"status": HTTPStatus.BAD_GATEWAY}, id="502"),
        pytest.param({"status": HTTPStatus.SERVICE_UNAVAILABLE}, id="503"),
        pytest.param({"exc": ClientError("boom")}, id="client_error"),
    ],
)
async def test_transport_failure_raises_api_error(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
    kwargs: dict[str, Any],
) -> None:
    """5xx HTTP and ``ClientError`` both surface as ``AbrpApiError``."""
    aioclient_mock.post(ABRP_GET_TLM_URL, **kwargs)

    with pytest.raises(AbrpApiError):
        await client.async_get_vehicles()


# ---------- AbrpTelemetryClient.async_get_one_shot (seed poll) -------------


@pytest.fixture(name="telemetry_client")
async def mock_telemetry_client(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> AbrpTelemetryClient:
    """Construct an ``AbrpTelemetryClient`` bound to HA's shared aiohttp session."""
    return AbrpTelemetryClient(
        async_get_clientsession(hass), ABRP_APP_KEY, ACCESS_TOKEN
    )


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="empty"),
        pytest.param(
            {"soc": {"frac": 0.5}, "power": {"w": 5000.0}, "voltage": {"v": 700.0}},
            id="populated",
        ),
    ],
)
async def test_async_get_one_shot_returns_parsed_json(
    telemetry_client: AbrpTelemetryClient,
    aioclient_mock: AiohttpClientMocker,
    payload: dict[str, Any],
) -> None:
    """``GET /2/tlm/{vehicleId}`` returns the bare ``OutputPoint`` JSON dict.

    The single-vehicle endpoint scopes ``vehicleId`` via the path, so the
    response body is the bare ``OutputPoint`` (no ``vehicleId`` field). Both
    the empty-frame and fully-populated cases parse identically — the
    coordinator's ``apply_frame`` does the null-filter + deep-merge on top.

    Also pins the request shape: ``Accept: application/json`` (else the
    server defaults back to SSE) + ``X-API-KEY`` (partner key) +
    ``X-ABRP-SESSION`` (OAuth access token), matching the live-probe
    auth contract.
    """
    aioclient_mock.get(ABRP_V2_TLM_ONE_SHOT_URL, json=payload)

    result = await telemetry_client.async_get_one_shot(MOCK_VEHICLE_ID)

    assert result == payload

    assert len(aioclient_mock.mock_calls) == 1
    method, url, _data, headers = aioclient_mock.mock_calls[0]
    assert method.lower() == "get"
    assert str(url) == ABRP_V2_TLM_ONE_SHOT_URL
    assert headers["Accept"] == "application/json"
    assert headers["X-API-KEY"] == ABRP_APP_KEY
    assert headers["X-ABRP-SESSION"] == ACCESS_TOKEN


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(HTTPStatus.UNAUTHORIZED, id="401"),
        pytest.param(HTTPStatus.FORBIDDEN, id="403"),
    ],
)
async def test_async_get_one_shot_auth_failure(
    telemetry_client: AbrpTelemetryClient,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
) -> None:
    """A 401/403 from the seed endpoint surfaces as ``AbrpAuthError``.

    Same auth boundary as :meth:`AbrpTelemetryClient.stream` — keeps the
    caller-side error handling identical between seed and stream paths.
    """
    aioclient_mock.get(ABRP_V2_TLM_ONE_SHOT_URL, status=status)

    with pytest.raises(AbrpAuthError):
        await telemetry_client.async_get_one_shot(MOCK_VEHICLE_ID)


@pytest.mark.parametrize(
    "response_kwargs",
    [
        pytest.param({"text": "null"}, id="null"),
        pytest.param({"json": []}, id="empty_list"),
        pytest.param({"json": [{"soc": {"frac": 0.5}}]}, id="list_of_dicts"),
        pytest.param({"json": "just a string"}, id="string"),
        pytest.param({"json": 42}, id="integer"),
    ],
)
async def test_async_get_one_shot_rejects_non_dict_payload(
    telemetry_client: AbrpTelemetryClient,
    aioclient_mock: AiohttpClientMocker,
    response_kwargs: dict[str, Any],
) -> None:
    """A non-dict JSON body for the one-shot endpoint raises ``AbrpApiError``.

    The API contract is "200 OK + JSON object"; anything else (JSON-null,
    list, scalar, string) is an upstream contract violation that must surface
    as the documented ``AbrpApiError`` boundary type rather than blowing up
    downstream with ``TypeError`` when the coordinator unpacks
    ``{**payload, "vehicleId": vid}``.

    The ``[null]`` case uses ``text="null"`` rather than ``json=None`` because
    ``aioclient_mock`` treats ``json=None`` as "no body" (mock helper line 190
    ``if json is not None: text = json_dumps(json)``) — an empty body would
    raise ``JSONDecodeError`` from ``response.json()`` and hit the malformed-
    JSON decode guard instead of the post-decode shape guard the test name
    advertises. ``text="null"`` writes ``b"null"`` so ``response.json()``
    returns Python ``None`` and falls through to ``isinstance(payload, dict)``.

    Sibling parametrize  —
    mirrored at ``test_async_get_vehicles_rejects_non_dict_payload`` and
    ``test_async_get_catalog_rejects_non_dict_payload`` so a future refactor
    that touches the shared decode pattern regresses LOUDLY at all three sites.

    Regression guard.
    """
    aioclient_mock.get(ABRP_V2_TLM_ONE_SHOT_URL, **response_kwargs)

    with pytest.raises(AbrpApiError):
        await telemetry_client.async_get_one_shot(MOCK_VEHICLE_ID)


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"status": HTTPStatus.INTERNAL_SERVER_ERROR}, id="500"),
        pytest.param({"status": HTTPStatus.BAD_GATEWAY}, id="502"),
        pytest.param({"exc": ClientError("boom")}, id="client_error"),
    ],
)
async def test_async_get_one_shot_transport_failure(
    telemetry_client: AbrpTelemetryClient,
    aioclient_mock: AiohttpClientMocker,
    kwargs: dict[str, Any],
) -> None:
    """5xx HTTP and ``ClientError`` both surface as ``AbrpApiError``.

    Seed is best-effort; the caller logs and proceeds silently on any
    non-auth failure rather than blocking setup. The client
    surfaces the public boundary error; the coordinator's
    ``async_seed_from_json_poll`` swallows it (test_coordinator covers the
    swallow path).
    """
    aioclient_mock.get(ABRP_V2_TLM_ONE_SHOT_URL, **kwargs)

    with pytest.raises(AbrpApiError):
        await telemetry_client.async_get_one_shot(MOCK_VEHICLE_ID)


# ---------- async_get_catalog timeout handling ------------------------------
#
# ``async_get_catalog`` uses a bare ``ClientTimeout(total=...)`` which raises a
# naked ``asyncio.TimeoutError`` — NOT a ``ClientError`` subclass. The catch
# band names ``TimeoutError`` explicitly so a hung catalog endpoint surfaces as
# ``AbrpApiError`` instead of crashing the coordinator refresh and freezing
# ``self._catalog`` at ``None``.


async def test_async_get_catalog_wraps_timeout_as_api_error(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A naked ``asyncio.TimeoutError`` from the catalog GET wraps to ``AbrpApiError``.

    Pins ``async_get_catalog``: the catch band must
    name ``TimeoutError`` explicitly alongside ``ClientError`` so that a
    bare ``ClientTimeout(total=...)`` budget exceedance surfaces as the
    public ``AbrpApiError`` boundary type — which the coordinator's
    ``(AbrpAuthError, AbrpApiError)`` fail-soft band then catches and
    degrades to an empty catalog. Without the wrapper the TimeoutError
    would propagate unchanged past the coordinator's narrow band, freeze
    ``self._catalog`` at ``None``, and force unbounded catalog refetch
    on every poll.

    The chained ``__cause__`` preserves the original TimeoutError so
    debug logs / diagnostics surface the underlying failure mode rather
    than just the wrapper label.
    """
    aioclient_mock.get(ABRP_V2_CATALOG_URL, exc=TimeoutError("catalog budget exceeded"))

    with pytest.raises(AbrpApiError) as excinfo:
        await client.async_get_catalog()

    assert isinstance(excinfo.value.__cause__, TimeoutError)


@pytest.mark.parametrize(
    "response_kwargs",
    [
        pytest.param({"text": "null"}, id="null"),
        pytest.param({"json": []}, id="empty_list"),
        pytest.param({"json": [{"typecode": "tesla:model3"}]}, id="list_of_dicts"),
        pytest.param({"json": "just a string"}, id="string"),
        pytest.param({"json": 42}, id="integer"),
    ],
)
async def test_async_get_catalog_rejects_non_dict_payload(
    client: AbrpClient,
    aioclient_mock: AiohttpClientMocker,
    response_kwargs: dict[str, Any],
) -> None:
    """A non-dict JSON body for the v2 catalog endpoint raises ``AbrpApiError``.

    Regression pin for the existing isinstance shape guard at
    ``AbrpClient.async_get_catalog`` (landed, commit ``e71f3189c37``).
    The guard is unpinned today; a future "simplify the check away" refactor
    would silently regress the failure class to ``AttributeError`` past the
    coordinator's ``(AbrpAuthError, AbrpApiError, TimeoutError)`` fail-soft
    band and freeze ``self._catalog`` at ``None``. Mirrors the sibling
    parametrize at ``test_async_get_one_shot_rejects_non_dict_payload``.
    """
    aioclient_mock.get(ABRP_V2_CATALOG_URL, **response_kwargs)

    with pytest.raises(AbrpApiError):
        await client.async_get_catalog()


# ---------- _parse_sse_event unit tests --------------------------------------


def test_parse_sse_event_single_data_line() -> None:
    """A single ``data: <json>`` line parses to the JSON dict."""
    event = 'data: {"vehicleId": 1, "soc": {"frac": 0.5}}'

    frame = _parse_sse_event(event)

    assert frame == {"vehicleId": 1, "soc": {"frac": 0.5}}


def test_parse_sse_event_multi_line_data_concatenates() -> None:
    r"""Per SSE spec multiple ``data:`` lines accumulate joined by ``\n``."""
    event = 'data: {"vehicleId": 1,\ndata: "soc": {"frac": 0.5}}'

    frame = _parse_sse_event(event)

    assert frame == {"vehicleId": 1, "soc": {"frac": 0.5}}


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(": keepalive", id="comment_only"),
        pytest.param(": heartbeat\n: still alive", id="multi_comment"),
        pytest.param("", id="empty"),
        pytest.param("\n\n", id="blank_lines"),
    ],
)
def test_parse_sse_event_comment_or_empty_returns_none(event: str) -> None:
    """Comment-only / empty events carry no ``data:`` payload — return None."""
    assert _parse_sse_event(event) is None


def test_parse_sse_event_malformed_json_raises_api_error() -> None:
    """Malformed JSON in a ``data:`` payload surfaces as ``AbrpApiError``."""
    event = "data: {not valid json"

    with pytest.raises(AbrpApiError):
        _parse_sse_event(event)


@pytest.mark.parametrize(
    "event",
    [
        pytest.param("data: [1, 2, 3]", id="json_array"),
        pytest.param('data: "just a string"', id="json_string"),
        pytest.param("data: 42", id="json_number"),
        pytest.param("data: null", id="json_null"),
    ],
)
def test_parse_sse_event_non_dict_payload_returns_none(event: str) -> None:
    """Decoded payload that isn't an object → dropped (not an exception)."""
    assert _parse_sse_event(event) is None


def test_parse_sse_event_dict_without_vehicle_id_returns_none() -> None:
    """A dict frame missing ``vehicleId`` is dropped (upstream-drift guard).

    Without ``vehicleId`` the coordinator can't route the frame to a
    vehicle's state; silently dropping with a debug log is safer than
    killing the SSE consumer task or merging into the wrong slot.
    """
    event = 'data: {"power": {"w": 100.0}}'

    assert _parse_sse_event(event) is None


# ---------- stream-level CR/CRLF normalization (G4) -------------------------


def _make_fake_session(chunks: list[bytes]) -> MagicMock:
    """Build a ``MagicMock`` aiohttp session whose ``GET`` yields ``chunks``.

    Plumbs the async-context-manager + ``response.content.iter_any()``
    chain that ``AbrpTelemetryClient.stream`` walks, with no real HTTP.
    """

    async def _iter_any() -> AsyncIterator[bytes]:
        for chunk in chunks:
            yield chunk

    response = MagicMock()
    response.status = HTTPStatus.OK
    response.content.iter_any = _iter_any
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=response)
    return session


async def test_stream_handles_crlf_split_across_chunks() -> None:
    r"""A ``\r\n`` pair spanning chunk boundaries yields exactly one frame.

    Regression coverage for G1: a lone trailing ``\r`` at the end of one
    chunk + the matching ``\n`` at the start of the next must be held
    together through the normalize so the buffer doesn't see a spurious
    extra ``\n\n`` and split one SSE event into two.
    """
    # Wire frame: ``data: {...}\r\n\r\n``. The first ``\r`` is the last
    # byte of chunk1; the matching ``\n`` opens chunk2.
    chunks = [
        b'data: {"vehicleId": 1, "soc": {"frac": 0.5}}\r',
        b"\n\r\n",
    ]
    session = _make_fake_session(chunks)
    client = AbrpTelemetryClient(session, "test-key", "test-tok")

    frames = [frame async for frame in client.stream([1])]

    assert len(frames) == 1
    assert frames[0] == {"vehicleId": 1, "soc": {"frac": 0.5}}


async def test_stream_handles_intact_crlf_boundary() -> None:
    r"""Belt-and-suspenders: a single intact ``\r\n\r\n`` boundary parses.

    Pairs with the split-boundary test: confirms the normalize works at
    all (a regression that flipped the replace-order would fail here but
    pass the split test).
    """
    chunks = [b'data: {"vehicleId": 1, "power": {"w": 100.0}}\r\n\r\n']
    session = _make_fake_session(chunks)
    client = AbrpTelemetryClient(session, "test-key", "test-tok")

    frames = [frame async for frame in client.stream([1])]

    assert len(frames) == 1
    assert frames[0] == {"vehicleId": 1, "power": {"w": 100.0}}


# ---------------------------------------------------------------------------
#  v2 catalog enrichment (api.py side)
# ---------------------------------------------------------------------------
#
# Names introduced by the skip-on-miss catalog-enrichment design:
#   * ``CatalogEntry`` — frozen dataclass for one ``vehicles[i]`` catalog entry
#   * ``_parse_catalog_entry`` — wire-record → CatalogEntry
#   * ``_enrich_with_catalog`` — (raw, catalog) → AbrpVehicle (skip-on-miss join)
#   * ``_str_or_none`` / ``_int_or_none`` — strict-typing helpers
#
# Names resolve via ``getattr`` so this module imports cleanly even when the
# symbols are later renamed in production; each test asserts its name resolved
# before exercising behaviour.

import homeassistant.components.abetterrouteplanner.api as _abrp_api_module  # noqa: E402

_CatalogEntry = getattr(_abrp_api_module, "CatalogEntry", None)
_parse_catalog_entry_fn = getattr(_abrp_api_module, "_parse_catalog_entry", None)
_enrich_with_catalog_fn = getattr(_abrp_api_module, "_enrich_with_catalog", None)
# A pure helper that resolves a
# vehicle's typecode against the v2 catalog via longest-prefix match and
# returns the composed display string (or ``None`` on a miss). Resolved
# lazily via ``getattr``
# so this module imports cleanly even when the symbols are later renamed in production.
_compute_device_model_fn = getattr(_abrp_api_module, "_compute_device_model", None)
# A token-aware
# prefix match on the ``:`` boundary. ``rivian:r1`` must NOT match the
# byte-prefix of ``rivian:r1s:25:foo`` — only typecode segments delimited
# by ``:`` participate. Resolved via getattr-default so the module loads
# cleanly even when the helper is later renamed.
_typecode_prefix_match_fn = getattr(_abrp_api_module, "_typecode_prefix_match", None)


def _build_raw_vehicle(**overrides: Any) -> AbrpVehicle:
    """Build an AbrpVehicle in the current dataclass shape (identity fields only).

    :class:`AbrpVehicle` carries identity fields plus a single composed
    ``device_model: str | None`` column (no per-field catalog columns such
    as ``manufacturer`` / ``model`` / ``title`` / years). This builder
    constructs the minimal vehicle from just the four identity fields.
    """
    base: dict[str, Any] = {
        "vehicle_id": MOCK_VEHICLE_ID,
        "name": MOCK_VEHICLE_NAME,
        "vehicle_model": MOCK_VEHICLE_MODEL,
        "paint": MOCK_PAINT,
    }
    base.update(overrides)
    return AbrpVehicle(**base)


def _sample_catalog_record(**overrides: Any) -> dict[str, Any]:
    """Build a ``vehicles[i]`` wire record shape.

    Outer keys are camelCase
    (v2 catalog is all-camel, no inner snake — divergent from SSE convention).
    """
    base: dict[str, Any] = {
        "typecode": "rivian:r1t-quad:22:135",
        "manufacturer": "Rivian",
        "model": "R1T",
        "title": "Rivian R1T Quad-Motor (2022, 135 kWh)",
        "startYear": 2022,
        "endYear": None,
        "batteryCapacityWh": 135000,
    }
    base.update(overrides)
    return base


_WIRE_TO_SNAKE: dict[str, str] = {
    "manufacturer": "manufacturer",
    "model": "model",
    "title": "title",
    "startYear": "start_year",
    "endYear": "end_year",
    "batteryCapacityWh": "battery_capacity_wh",
}


# ---- _parse_catalog_entry -------------------------------------------------


def test_parse_catalog_entry_happy_path() -> None:
    """Happy-path wire record → CatalogEntry projects every field."""
    assert _parse_catalog_entry_fn is not None, "_parse_catalog_entry not implemented"

    entry = _parse_catalog_entry_fn(_sample_catalog_record())

    assert entry.typecode == "rivian:r1t-quad:22:135"
    assert entry.manufacturer == "Rivian"
    assert entry.model == "R1T"
    assert entry.title == "Rivian R1T Quad-Motor (2022, 135 kWh)"
    assert entry.start_year == 2022
    assert entry.end_year is None
    assert entry.battery_capacity_wh == 135000


@pytest.mark.parametrize(
    ("field", "wire_value", "expected"),
    [
        # Empty string — contract: empty stays empty.
        pytest.param("manufacturer", "", None, id="manufacturer_empty_string"),
        pytest.param("model", "", None, id="model_empty_string"),
        pytest.param("title", "", None, id="title_empty_string"),
        # Whitespace-only — contract: whitespace-only collapses to
        # ``None``. The earlier shape accepted any non-empty string
        # verbatim, so ``"   "`` would leak past the truthy gate and
        # false-positive the manufacturer+model filter in
        # ``_compute_device_model`` (or render as visible whitespace in
        # the title segment). The current helper collapses to None.
        pytest.param("manufacturer", "   ", None, id="manufacturer_whitespace_only"),
        pytest.param("model", "   ", None, id="model_whitespace_only"),
        pytest.param("title", "   ", None, id="title_whitespace_only"),
        # Whitespace-padded — contract: whitespace-padded values are
        # stripped at the parse boundary (``"  Rivian "`` → ``"Rivian"``)
        # so downstream consumers see the trimmed token verbatim;
        # ``_str_or_none`` strips first.
        pytest.param(
            "manufacturer", "  Rivian  ", "Rivian", id="manufacturer_whitespace_padded"
        ),
        pytest.param("model", "  R1S  ", "R1S", id="model_whitespace_padded"),
        pytest.param(
            "title", "  Dual Motor  ", "Dual Motor", id="title_whitespace_padded"
        ),
    ],
)
def test_parse_catalog_entry_whitespace_normalisation(
    field: str, wire_value: str, expected: str | None
) -> None:
    """Catalog string fields normalise empty / whitespace-only / padded at parse boundary.

    Single-site normalisation: ``_str_or_none`` is the one consumer-
    facing seam for catalog string fields. Three upstream-drift
    shapes converge on the same contract:

    * ``""`` (spec-required-but-empty, observed on ABRP) → ``None``.
    * ``"   "`` (whitespace-only, an ABRP catalog accident) → ``None``.
    * ``"  X  "`` (whitespace-padded) → ``"X"`` (stripped).

    The earlier ``_str_or_none`` shape accepted any non-empty string
    verbatim — whitespace-only would leak past the ``if isinstance(
    value, str) and value`` gate (truthy), and whitespace-padded would
    survive unchanged. The helper now strips first and collapses
    whitespace-only to None.

    Replaces the earlier ``test_parse_catalog_entry_empty_string_normalised_to_none``
    (test name broadened to reflect the wider contract); the
    empty-string cases are preserved as regression pins.
    """
    assert _parse_catalog_entry_fn is not None, "_parse_catalog_entry not implemented"

    entry = _parse_catalog_entry_fn(_sample_catalog_record(**{field: wire_value}))

    assert getattr(entry, _WIRE_TO_SNAKE[field]) == expected


@pytest.mark.parametrize(
    ("field", "wire_value"),
    [
        pytest.param("startYear", True, id="startyear_bool_true_rejected"),
        pytest.param("startYear", False, id="startyear_bool_false_rejected"),
        pytest.param("startYear", "2022", id="startyear_string_int_rejected"),
        pytest.param("startYear", 2022.0, id="startyear_float_rejected"),
        pytest.param("endYear", True, id="endyear_bool_rejected"),
        pytest.param("batteryCapacityWh", 135000.0, id="capacity_float_rejected"),
        pytest.param("batteryCapacityWh", "135000", id="capacity_string_int_rejected"),
    ],
)
def test_parse_catalog_entry_strict_int_rejects_wrong_types(
    field: str, wire_value: Any
) -> None:
    """Strict-typing on int catalog fields.

    bool ⊂ int in Python (``isinstance(True, int) is True``) so unguarded
    integer parsing accepts bools —
    we explicitly reject. Strings-that-look-like-ints and floats-with-no-
    fractional are also rejected: ABRP documents these fields as int32,
    so divergence is upstream drift that should fail loudly (None at the
    parse boundary, sensor renders as unknown) rather than silently
    coercing. Catches accidental ``int(value)`` shortcuts in the parser.
    """
    assert _parse_catalog_entry_fn is not None, "_parse_catalog_entry not implemented"

    entry = _parse_catalog_entry_fn(_sample_catalog_record(**{field: wire_value}))

    assert getattr(entry, _WIRE_TO_SNAKE[field]) is None


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("manufacturer", id="manufacturer_missing"),
        pytest.param("model", id="model_missing"),
        pytest.param("title", id="title_missing"),
        pytest.param("startYear", id="start_year_missing"),
        pytest.param("endYear", id="end_year_missing"),
        pytest.param("batteryCapacityWh", id="battery_capacity_missing"),
    ],
)
def test_parse_catalog_entry_missing_optional_field_is_none(field: str) -> None:
    """Optional catalog field absent from the wire → CatalogEntry field is ``None``.

    Defensive: ABRP's catalog spec marks several fields nullable and the
    parse must fall through cleanly to None rather than raising KeyError
    or stringifying the missing value as ``"None"``.
    """
    assert _parse_catalog_entry_fn is not None, "_parse_catalog_entry not implemented"

    record = _sample_catalog_record()
    del record[field]

    entry = _parse_catalog_entry_fn(record)

    assert getattr(entry, _WIRE_TO_SNAKE[field]) is None


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("manufacturer", id="manufacturer_null"),
        pytest.param("startYear", id="start_year_null"),
        pytest.param("batteryCapacityWh", id="battery_capacity_null"),
    ],
)
def test_parse_catalog_entry_explicit_null_is_none(field: str) -> None:
    """Wire field explicitly ``null`` → CatalogEntry field is ``None``.

    Distinct from "missing" (absent key): JSON ``null`` deserialises to
    Python ``None``. The parser's helpers must reject ``None`` upfront
    (``_str_or_none`` / ``_int_or_none`` both check non-None) rather than
    failing inside ``str(None)`` or ``int(None)``.
    """
    assert _parse_catalog_entry_fn is not None, "_parse_catalog_entry not implemented"

    entry = _parse_catalog_entry_fn(_sample_catalog_record(**{field: None}))

    assert getattr(entry, _WIRE_TO_SNAKE[field]) is None


# ---------------------------------------------------------------------------
# _compute_device_model + reshaped _enrich_with_catalog
# ---------------------------------------------------------------------------
#
# The catalog's display metadata is composed once into
# a single ``device_model`` column on ``AbrpVehicle`` and surfaced via
# :attr:`DeviceInfo.model` on the per-vehicle device. The composition is
# longest-typecode-prefix-match (not exact ``dict.get``) so a vehicle whose
# typecode is a suffix-decorated variant of a catalog ancestor still
# resolves.
#
# Helper signature:
#
#     def _compute_device_model(
#         typecode: str, catalog: Mapping[str, CatalogEntry]
#     ) -> str | None
#
# Build formula:
#
#     parts = [f"{best.manufacturer} {best.model}"]
#     if best.start_year is not None and best.end_year is not None:
#         parts.append(f"{best.start_year}-{best.end_year}")
#     elif best.start_year is not None:
#         parts.append(str(best.start_year))
#     # else: year segment dropped (covers no-startYear and endYear-only)
#     if best.title and best.title.strip():
#         parts.append(best.title)
#     return " ".join(parts)
#
# the helper does not
# iterate a registry, so the parametrize floor is per-shape — each case
# below pins one cell in the yearxtitle state machine plus one
# longest-prefix-wins case plus one corrupted-catalog filter case.
# ---------------------------------------------------------------------------


def _make_entry(
    typecode: str = "rivian:r1s:25:c3-53g:dual",
    *,
    manufacturer: str | None = "Rivian",
    model: str | None = "R1S",
    title: str | None = "Dual Motor",
    start_year: int | None = 2025,
    end_year: int | None = None,
    battery_capacity_wh: int | None = None,
) -> Any:
    """Build a CatalogEntry for the prefix-match helper tests.

    ``_CatalogEntry`` resolves to :class:`CatalogEntry`. The factory exists
    for readability in the parametrize bodies below.
    """
    assert _CatalogEntry is not None, "CatalogEntry not available"
    return _CatalogEntry(
        typecode=typecode,
        manufacturer=manufacturer,
        model=model,
        title=title,
        start_year=start_year,
        end_year=end_year,
        battery_capacity_wh=battery_capacity_wh,
    )


# Probe sentinel objects
# would be overkill here — every parametrize case below carries a
# well-typed catalog dict, and "no catalog entries" is a single shape
# (the literal empty dict).


@pytest.mark.parametrize(
    ("typecode", "catalog", "expected"),
    [
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {},
            None,
            id="empty_catalog_returns_none",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {"audi:q4:45:24:77:meb:sb:awd": _make_entry("audi:q4:45:24:77:meb:sb:awd")},
            None,
            id="no_prefix_match_returns_none",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    manufacturer="Rivian",
                    model="R1S",
                    title="Dual Motor",
                    start_year=2024,
                    end_year=2025,
                ),
            },
            "Rivian R1S 2024-2025 Dual Motor",
            id="both_years_present_yields_range_segment",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    start_year=2025,
                    end_year=None,
                ),
            },
            "Rivian R1S 2025 Dual Motor",
            id="start_year_only_yields_bare_year_segment",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    start_year=None,
                    end_year=2023,
                ),
            },
            "Rivian R1S Dual Motor",
            id="end_year_only_drops_year_segment_entirely",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    start_year=None,
                    end_year=None,
                ),
            },
            "Rivian R1S Dual Motor",
            id="both_years_missing_drops_year_segment",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    title=None,
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025",
            id="title_absent_yields_no_title_segment",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    title="   ",
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025",
            id="title_whitespace_only_dropped_via_strip_guard",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual:perf",
            {
                "rivian": _make_entry(
                    "rivian",
                    manufacturer="Rivian",
                    model="(generic)",
                    title=None,
                    start_year=None,
                ),
                "rivian:r1s:25": _make_entry(
                    "rivian:r1s:25",
                    manufacturer="Rivian",
                    model="R1S",
                    title="2025 lineup",
                    start_year=2025,
                ),
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    manufacturer="Rivian",
                    model="R1S",
                    title="Dual Motor",
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025 Dual Motor",
            id="longest_prefix_wins_across_three_ancestors",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual:perf",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    manufacturer=None,
                    model="R1S",
                    title="Dual Motor",
                    start_year=2025,
                ),
                "rivian:r1s:25": _make_entry(
                    "rivian:r1s:25",
                    manufacturer="Rivian",
                    model="R1S",
                    title="2025 lineup",
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025 2025 lineup",
            id="longest_prefix_with_null_manufacturer_falls_back_to_shorter",
        ),
        # the catalog's only entry
        # is a strict byte-prefix of the target typecode but is NOT a token
        # ancestor on the ``:`` delimiter (``rivian:r1`` vs
        # ``rivian:r1s:25:foo``). Byte-prefix match would falsely pick
        # ``rivian:r1`` and emit a misleading display; token-prefix
        # correctly rejects so ``device_model`` stays ``None``.
        pytest.param(
            "rivian:r1s:25:foo",
            {
                "rivian:r1": _make_entry(
                    "rivian:r1",
                    manufacturer="Rivian",
                    model="R1",
                    title="(generic)",
                    start_year=2022,
                ),
            },
            None,
            id="token_boundary_rejects_byte_prefix_non_ancestor",
        ),
        #  F-API-TITLE auto-resolve via _str_or_none tightening:
        # whitespace-padded ``title`` from the catalog wire must not leak
        # padding into the composed display string. legacy the helper
        # appends ``best.title`` verbatim (asymmetric guard
        # ``if best.title and best.title.strip(): parts.append(best.title)``);
        # current ``_str_or_none`` strips at the parse boundary so the
        # appended segment is already trimmed.
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    manufacturer="Rivian",
                    model="R1S",
                    title="  Dual Motor  ",
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025 Dual Motor",
            id="whitespace_padded_title_stripped_in_display",
        ),
    ],
)
def test_compute_device_model_parametrized(
    typecode: str,
    catalog: dict[str, Any],
    expected: str | None,
) -> None:
    """Pin :func:`_compute_device_model` across the yearxtitle state machine.

    Each case exercises one cell of the composition formula plus the
    longest-prefix selection logic.
    """
    assert _compute_device_model_fn is not None, "_compute_device_model not implemented"

    assert _compute_device_model_fn(typecode, catalog) == expected


# ---- _typecode_prefix_match (refinement) ----------------
#
# Standalone unit pin for the token-aware prefix-match predicate. The
# parent ``_compute_device_model`` parametrize above carries one
# integration-level row covering the token-boundary guard
# (``token_boundary_rejects_byte_prefix_non_ancestor``); this sibling
# parametrize exercises the predicate in isolation so a regression
# that flipped the comparison to plain ``str.startswith`` surfaces
# with a precise failure message rather than as a downstream
# composed-string mismatch.
#
# Sketch:
#
#     def _typecode_prefix_match(candidate: str, target: str) -> bool:
#         return candidate == target or target.startswith(candidate + ":")


@pytest.mark.parametrize(
    ("candidate", "target", "expected"),
    [
        pytest.param("rivian:r1s", "rivian:r1s", True, id="exact_equality"),
        pytest.param(
            "rivian:r1s",
            "rivian:r1s:25:foo",
            True,
            id="strict_token_ancestor",
        ),
        pytest.param(
            "rivian:r1",
            "rivian:r1s:25:foo",
            False,
            id="byte_prefix_but_not_token_ancestor",
        ),
        pytest.param(
            "rivian:r1s",
            "tesla:model3:2024",
            False,
            id="disjoint",
        ),
        pytest.param(
            "rivian:r1s:25:foo",
            "rivian:r1s",
            False,
            id="candidate_longer_than_target",
        ),
    ],
)
def test_typecode_prefix_match_parametrized(
    candidate: str,
    target: str,
    expected: bool,
) -> None:
    """Pin :func:`_typecode_prefix_match` token-aware comparison invariants.

    Five cases cover the predicate's correctness floor:

    * **exact_equality** — identical typecodes match (the degenerate
      case where the catalog entry is the target verbatim).
    * **strict_token_ancestor** — ``candidate`` is a strict token-level
      ancestor of ``target``; the next character after ``candidate`` in
      ``target`` must be ``:``.
    * **byte_prefix_but_not_token_ancestor** — the load-bearing negative
      : ``rivian:r1`` is a byte-prefix of
      ``rivian:r1s:25:foo`` but is NOT a token ancestor. A naive
      ``target.startswith(candidate)`` returns True here; the helper
      must reject.
    * **disjoint** — no shared prefix at all.
    * **candidate_longer_than_target** — ``candidate`` cannot prefix a
      shorter ``target``; the predicate must be asymmetric.
    """
    assert _typecode_prefix_match_fn is not None, (
        "_typecode_prefix_match not implemented"
    )

    assert _typecode_prefix_match_fn(candidate, target) is expected


# ---- _enrich_with_catalog (current — single composed ``device_model``) ----


def test_enrich_with_catalog_hit_populates_device_model() -> None:
    """Catalog hit → ``device_model`` carries the composed display string.

    Identity fields carry through unchanged; :class:`AbrpVehicle` has no
    per-field catalog columns — only ``device_model`` is set when the
    typecode prefix-matches a catalog entry.
    """
    assert _enrich_with_catalog_fn is not None, "_enrich_with_catalog must exist"
    assert _CatalogEntry is not None, "CatalogEntry must exist"

    raw = _build_raw_vehicle(vehicle_model="rivian:r1s:25:c3-53g:dual:perf")
    catalog = {
        "rivian:r1s:25:c3-53g:dual": _make_entry(
            "rivian:r1s:25:c3-53g:dual",
            manufacturer="Rivian",
            model="R1S",
            title="Dual Motor",
            start_year=2025,
        ),
    }

    result = _enrich_with_catalog_fn(raw, catalog)

    assert result.device_model == "Rivian R1S 2025 Dual Motor"
    assert result.vehicle_id == raw.vehicle_id
    assert result.vehicle_model == raw.vehicle_model


def test_enrich_with_catalog_miss_device_model_is_none() -> None:
    """Catalog miss → ``device_model`` stays ``None``; identity preserved.

    Skip-on-miss invariant (adversarial row 2): no typecode-string parsing
    fallback.
    """
    assert _enrich_with_catalog_fn is not None, "_enrich_with_catalog must exist"

    raw = _build_raw_vehicle(vehicle_model="rivian:r2:26:ncma91:rwd:w21")

    result = _enrich_with_catalog_fn(raw, {})

    assert result.device_model is None
    assert result.vehicle_model == "rivian:r2:26:ncma91:rwd:w21"
    assert result.vehicle_id == raw.vehicle_id


def test_enrich_with_catalog_hit_populates_device_manufacturer() -> None:
    """Catalog hit → ``device_manufacturer`` carries the catalog's make.

    Sibling of ``test_enrich_with_catalog_hit_populates_device_model``:
    the same prefix-matched ``CatalogEntry`` populates both columns on
    :class:`AbrpVehicle`.
    """
    assert _enrich_with_catalog_fn is not None, "_enrich_with_catalog must exist"
    assert _CatalogEntry is not None, "CatalogEntry must exist"

    raw = _build_raw_vehicle(vehicle_model="rivian:r1s:25:c3-53g:dual:perf")
    catalog = {
        "rivian:r1s:25:c3-53g:dual": _make_entry(
            "rivian:r1s:25:c3-53g:dual",
            manufacturer="Rivian",
            model="R1S",
            title="Dual Motor",
            start_year=2025,
        ),
    }

    result = _enrich_with_catalog_fn(raw, catalog)

    assert result.device_manufacturer == "Rivian"


def test_enrich_with_catalog_miss_device_manufacturer_is_none() -> None:
    """Catalog miss → ``device_manufacturer`` stays ``None``.

    Mirrors the skip-on-miss invariant pinned by
    ``test_enrich_with_catalog_miss_device_model_is_none``: no
    typecode-string parsing fallback.
    """
    assert _enrich_with_catalog_fn is not None, "_enrich_with_catalog must exist"

    raw = _build_raw_vehicle(vehicle_model="rivian:r2:26:ncma91:rwd:w21")

    result = _enrich_with_catalog_fn(raw, {})

    assert result.device_manufacturer is None
