"""Fixtures for the A Better Routeplanner integration tests."""

import asyncio
import base64
from collections.abc import AsyncIterator, Generator
from http import HTTPStatus
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.abetterrouteplanner.api import AbrpVehicle
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

USER_SUB = "user-sub-12345"
REDIRECT_URI = "https://example.com/auth/external/callback"

# v1 API surface — these values pin the wire contract that api.py +
# config_flow picker depend on.
ABRP_API_BASE = "https://api.iternio.com/1"
ABRP_API_V2_BASE = "https://api.iternio.com/2"
ABRP_GET_TLM_URL = f"{ABRP_API_BASE}/session/get_tlm"
ABRP_VEHICLE_LIST_URL = f"{ABRP_API_V2_BASE}/vehicle/_list"

# Sample identity drawn from /tmp/abrp_garage_fixture.json (live probe).
MOCK_VEHICLE_ID = 941349991303
MOCK_VEHICLE_NAME = "Rivian R2 2027 Standard Long Range"
MOCK_VEHICLE_MODEL = "rivian:r2:26:ncma91:rwd:w21"
MOCK_PAINT = "WHITE"

# Second vehicle for multi-vehicle scenarios (snapshot + dynamic disappearance).
MOCK_VEHICLE_ID_2 = 524289123456
MOCK_VEHICLE_NAME_2 = "Rivian R1S 2024 Quad Max"
MOCK_VEHICLE_MODEL_2 = "rivian:r1s:24:max:tri:w22"
MOCK_PAINT_2 = "BLACK"

# Deterministic, on-domain ``sub`` for sensor / device tests so Syrupy
# snapshots stay readable and stable across runs. Distinct from the broader
# ``USER_SUB`` used by config-flow / init tests so a snapshot diff that
# accidentally picks up an unscoped identifier is visually obvious.
SENSOR_TEST_SUB = "abrp-test-sub"


def build_vehicle_record(
    vehicle_id: int = MOCK_VEHICLE_ID,
    name: str = MOCK_VEHICLE_NAME,
    vehicle_model: str = MOCK_VEHICLE_MODEL,
    paint: str | None = MOCK_PAINT,
) -> dict[str, Any]:
    """Build one entry of the ``result`` array as returned by /1/session/get_tlm.

    Shape mirrors the live probe at ``/tmp/abrp_garage_fixture.json``. Many
    fields are irrelevant to vehicle enumeration (telemetry / OBD / streaming)
    but are included so the fixture matches what the real endpoint emits.
    """
    return {
        "vehicle_id": vehicle_id,
        "tlm_type": None,
        "ota_tlm_type": None,
        "tlm_authorized": None,
        "car_model": vehicle_model,
        "always_log": False,
        "has_settings": True,
        "vin_hash": None,
        "vin_hashes": None,
        "tlm_is_streaming": False,
        "tlm_can_stream": None,
        "tlm_streaming_type": None,
        "tlm_region_error": None,
        "obd_ble_device_ids": None,
        "obd_ble_device_id": None,
        "is_connected": False,
        "ota_is_connected": False,
        "local_is_connected": False,
        "tlm_time": 0,
        "name": name,
        "paint": paint,
        "active_config": None,
        "tlm": None,
        "tlm_intervention_ids": None,
        "owner_id": 2755291,
        "owner_name": "TempAccount",
        "owner_email": "tester@example.invalid",
    }


def build_garage_response(
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap ``records`` in the v1 envelope returned by /1/session/get_tlm.

    Pass ``records=None`` (the default) for the canonical single-vehicle
    garage; pass ``[]`` for an empty account; pass a list of multiple records
    built via :func:`build_vehicle_record` for N>1 cases.
    """
    if records is None:
        records = [build_vehicle_record()]
    return {
        "status": "ok",
        "result": records,
        "extra": {"settings_update_time": 0, "settings_version": 0},
    }


def build_catalog_response(
    vehicles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap ``vehicles`` in the v2 envelope returned by /2/vehicle/_list.

    Pass ``vehicles=None`` (the default) for an empty catalog response — the
    common shape for tests that need the endpoint to succeed but don't care
    about catalog enrichment. The full live catalog is ~1100 entries; tests
    that need specific entries should pass concrete records.
    """
    if vehicles is None:
        vehicles = []
    return {"display": [], "options": [], "vehicles": vehicles}


@pytest.fixture(name="mock_abrp_vehicles_response")
def mock_abrp_vehicles_response() -> dict[str, Any]:
    """Canonical single-vehicle garage response.

    Override per-test by calling :func:`build_garage_response` with custom
    ``records`` and assigning the result to ``aioclient_mock.post(...)``.
    """
    return build_garage_response()


@pytest.fixture(name="mock_get_tlm")
def mock_get_tlm(
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_vehicles_response: dict[str, Any],
) -> None:
    """Register ``POST /1/session/get_tlm`` to return the default garage."""
    aioclient_mock.post(ABRP_GET_TLM_URL, json=mock_abrp_vehicles_response)


async def complete_oauth_callback(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    flow_id: str,
) -> None:
    """Drive the OAuth external callback for an in-progress flow."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {"flow_id": flow_id, "redirect_uri": REDIRECT_URI},
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"


def build_id_token(sub: str = USER_SUB, *, email: str | None = None) -> str:
    """Build a fake JWT id_token with the given ``sub`` (and optional ``email``).

    The returned token has the form ``header.payload.signature``; only the
    payload is real (base64-urlsafe JSON), the header and signature are opaque
    placeholders since the integration only inspects the payload.

    ``email`` is omitted from the payload when ``None`` (the default) so existing
    call sites that only pass ``sub`` produce the same shape as before. Pass
    an explicit ``""`` to exercise the empty-string branch in callers that
    treat ``not email`` as absent.
    """
    payload_dict: dict[str, Any] = {"sub": sub}
    if email is not None:
        payload_dict["email"] = email
    payload = json.dumps(payload_dict).encode()
    payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    return f"header.{payload_b64}.signature"


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the OAuth token expiration time."""
    return time.time() + 86400


@pytest.fixture(name="id_token_sub")
def mock_id_token_sub() -> str:
    """Fixture providing the ``sub`` claim to embed in the id_token."""
    return USER_SUB


@pytest.fixture(name="token_entry")
def mock_token_entry(expires_at: float, id_token_sub: str) -> dict[str, Any]:
    """Fixture for OAuth ``token`` data for a ConfigEntry."""
    return {
        "access_token": "mock-access-token",
        "refresh_token": "mock-refresh-token",
        "token_type": "Bearer",
        "expires_at": expires_at,
        "id_token": build_id_token(id_token_sub),
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Return the default mocked config entry.

    ``CONF_VEHICLE_IDS`` is set to an empty list: ``__init__.py`` reads it via
    direct ``entry.data[CONF_VEHICLE_IDS]`` access, so the key must be present
    or setup raises ``KeyError``. An empty list keeps these legacy fixtures
    minimal — no vehicles selected means no SSE task spawns, so tests
    using this fixture don't need ``mock_sse_client``.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [],
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.abetterrouteplanner.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="mock_abrp_vehicles")
def mock_abrp_vehicles() -> list[AbrpVehicle]:
    """Default 2-vehicle garage returned by the patched ``AbrpClient``.

    Sensor + coordinator tests parametrize on this fixture to vary the
    coordinator payload without re-patching the client per-test.
    """
    return [
        AbrpVehicle(
            vehicle_id=MOCK_VEHICLE_ID,
            name=MOCK_VEHICLE_NAME,
            vehicle_model=MOCK_VEHICLE_MODEL,
            paint=MOCK_PAINT,
        ),
        AbrpVehicle(
            vehicle_id=MOCK_VEHICLE_ID_2,
            name=MOCK_VEHICLE_NAME_2,
            vehicle_model=MOCK_VEHICLE_MODEL_2,
            paint=MOCK_PAINT_2,
        ),
    ]


@pytest.fixture(name="mock_abrp_client")
def mock_abrp_client(
    mock_abrp_vehicles: list[AbrpVehicle],
) -> Generator[AsyncMock]:
    """Patch ``AbrpClient.async_get_vehicles`` with a configurable mock.

    The mock's ``return_value`` is set to the 2-vehicle
    ``mock_abrp_vehicles`` list (the same list object on every call — no
    current test mutates it in place; tests that need to alter per-refresh
    behaviour reassign ``return_value`` / ``side_effect`` directly on the
    yielded mock). The patch targets the source module (not a downstream
    import) so it covers both the coordinator's instantiation path and any
    direct ``AbrpClient(...)`` usage in config-flow code.

    Also patches ``async_get_catalog`` with an empty-dict default so the
    garage coordinator's lazy-once catalog fetch doesn't reach the real
    network. Tests that exercise catalog enrichment behaviour can
    nest their own ``with patch(...)`` to override the return value or
    inject a side_effect for the catalog endpoint specifically.
    """
    with (
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpClient.async_get_vehicles",
            autospec=True,
            return_value=mock_abrp_vehicles,
        ) as mock_client,
        patch(
            "homeassistant.components.abetterrouteplanner.api.AbrpClient.async_get_catalog",
            autospec=True,
            return_value={},
        ),
    ):
        yield mock_client


@pytest.fixture(name="config_entry_with_vehicles")
def mock_config_entry_with_vehicles(
    token_entry: dict[str, Any],
) -> MockConfigEntry:
    """Return a config entry with the first vehicle preselected.

    Used by sensor + coordinator tests that need a populated
    ``CONF_VEHICLE_IDS`` list without driving the full config-flow picker step.
    Only the first vehicle is selected so snapshot tests can assert the
    filter behaviour (selected entity emitted, unselected vehicle ignored).

    ``unique_id`` is set to :data:`SENSOR_TEST_SUB` (the deterministic
    on-domain stand-in for a JWT ``sub`` claim) because both device
    identifiers and entity unique_ids are scoped by ``entry.unique_id`` —
    keeping the value stable and readable across runs is required for the
    Syrupy snapshots to diff cleanly.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID)],
        },
    )


# Telemetry fixtures -----------------------------------------------------------


def build_telemetry_frame(
    vehicle_id: int,
    *,
    soc: float | None = None,
    power: float | None = None,
    voltage: float | None = None,
    range_m: float | None = None,
    battery_temp_c: float | None = None,
    charging_state: str | None = None,
) -> dict[str, Any]:
    """Build a partial ``OutputPointWithVehicleId`` frame.

    Mirrors the v2 SSE wire shape (probe-confirmed): ``vehicleId`` plus zero
    or more nested per-metric records (``soc.frac``, ``power.w``,
    ``voltage.v``, ``estimatedBatteryRange.m``, ``batteryTemperature.c``,
    ``chargingState.state``). Outer-camel / inner-snake follows ABRP's v2
    telemetry wire-key naming. The frame is a *delta* — the coordinator
    merges into its per-vehicle state, so tests typically construct
    one-metric frames to verify partial-update semantics.

    Values default to ``None`` (omitted from the frame), not ``0`` — a
    ``None`` placeholder would never appear on the wire and would break
    the "missing key" branch tests for ``available``.

    ``charging_state`` carries the categorical ENUM leaf: the value is the
    raw upstream wire member (``"CHARGING_AC"`` etc.), emitted as
    ``{"chargingState": {"state": <value>}}`` only when set — same
    omit-when-None pattern as the numeric metrics. Malformed shapes the
    helper can't express (non-dict block, missing ``state``) are built as
    raw dicts directly in the value_fn tests.
    """
    frame: dict[str, Any] = {"vehicleId": vehicle_id}
    if soc is not None:
        frame["soc"] = {"frac": soc}
    if power is not None:
        frame["power"] = {"w": power}
    if voltage is not None:
        frame["voltage"] = {"v": voltage}
    if range_m is not None:
        frame["estimatedBatteryRange"] = {"m": range_m}
    if battery_temp_c is not None:
        frame["batteryTemperature"] = {"c": battery_temp_c}
    if charging_state is not None:
        frame["chargingState"] = {"state": charging_state}
    return frame


class _FrameStream:
    """Async iterator backing ``mock_sse_client``.

    Yields any queued frames in order, then blocks indefinitely so the
    long-lived SSE consumer task stays alive until the test unloads the
    entry (which cancels the task). ``asyncio.CancelledError`` exits the
    iterator cleanly.
    """

    def __init__(self, frames: list[dict[str, Any]]) -> None:
        self._frames = list(frames)

    def __aiter__(self) -> _FrameStream:
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._frames:
            return self._frames.pop(0)
        try:
            await asyncio.sleep(86400)
        except asyncio.CancelledError:
            raise StopAsyncIteration from None
        raise StopAsyncIteration

    async def aclose(self) -> None:
        """No-op cleanup to match the real async-generator shape.

        ``AbrpTelemetryClient.stream`` is a real ``async def`` with ``yield``,
        so calling it returns an async-generator object that carries an
        ``aclose()``. The SSE consumer's ``finally`` block awaits that
        cleanup. This class-based test iterator doesn't have native
        ``aclose``, so we provide a no-op so tests don't blow up at unload.
        """


@pytest.fixture(name="mock_seed_responses")
def mock_seed_responses() -> Generator[AsyncMock]:
    """Patch ``AbrpTelemetryClient.async_get_one_shot`` with per-vehicle returns.

    Default behaviour: an empty dict is returned for any vehicle id not in the
    table — equivalent to the wire returning ``{}`` (no metric data yet,
    vehicle has been parked offline since boot).

    Tests assign to the mock's ``.responses`` dict to customize per-vehicle
    payloads or push exceptions:

    .. code-block:: python

        mock_seed_responses.responses[MOCK_VEHICLE_ID] = {"soc": {"frac": 0.42}}
        mock_seed_responses.responses[OTHER_ID] = AbrpApiError("boom")

    ``create=True`` so the patch applies cleanly even if
    :meth:`AbrpTelemetryClient.async_get_one_shot` is later renamed —
    the fallback fixture setup keeps the imports working.
    """
    responses: dict[int, Any] = {}

    async def _per_vehicle(vehicle_id: int) -> dict[str, Any]:
        outcome = responses.get(vehicle_id, {})
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    with patch(
        "homeassistant.components.abetterrouteplanner.api.AbrpTelemetryClient.async_get_one_shot",
        create=True,
        side_effect=_per_vehicle,
    ) as mock:
        mock.responses = responses
        yield mock


@pytest.fixture(name="mock_sse_client")
def mock_sse_client() -> Generator[MagicMock]:
    """Patch ``AbrpTelemetryClient.stream`` with a configurable async iterator.

    Default behaviour: stream yields nothing and blocks indefinitely so the
    background SSE task stays alive after ``async_setup_entry``. Tests that
    want to push frames assign to ``mock_sse_client.frames``; tests that
    want to simulate disconnect/auth-failure assign ``side_effect`` on the
    underlying mock just like any other ``MagicMock``.

    Reset between calls: the *mock* records calls but a fresh ``_FrameStream``
    is returned each invocation, mirroring real SSE reconnect behaviour
    where each ``stream(...)`` call opens a new connection.
    """
    frames: list[list[dict[str, Any]]] = [[]]

    def _factory(*_args: Any, **_kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        return _FrameStream(frames[0])

    with patch(
        "homeassistant.components.abetterrouteplanner.api.AbrpTelemetryClient.stream",
        side_effect=_factory,
    ) as mock:
        mock.set_frames = lambda new_frames: frames.__setitem__(0, list(new_frames))
        yield mock
