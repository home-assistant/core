"""Fixtures for the A Better Routeplanner integration tests."""

import base64
from collections.abc import Generator
from datetime import datetime
from http import HTTPStatus
import json
import time
from typing import Any
from unittest.mock import AsyncMock, patch

from aioabrp import (
    AbrpApiError,
    AbrpVehicle,
    ChargingState,
    ConnectionEvent,
    MetricValue,
    Telemetry,
    VehicleModelDisplay,
)
import pytest

from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

USER_SUB = "user-sub-12345"
REDIRECT_URI = "https://example.com/auth/external/callback"

# Sample vehicle identity used across the tests.
MOCK_VEHICLE_ID = 941349991303
MOCK_VEHICLE_NAME = "Rivian R2 2027 Standard Long Range"
MOCK_VEHICLE_MODEL = "rivian:r2:26:ncma91:rwd:w21"
MOCK_PAINT = "WHITE"

# Second vehicle for multi-vehicle scenarios (snapshot + disappearance).
MOCK_VEHICLE_ID_2 = 524289123456
MOCK_VEHICLE_NAME_2 = "Rivian R1S 2024 Quad Max"
MOCK_VEHICLE_MODEL_2 = "rivian:r1s:24:max:tri:w22"
MOCK_PAINT_2 = "BLACK"

# Deterministic, on-domain ``sub`` for sensor / device tests so Syrupy
# snapshots stay readable and stable across runs. Distinct from the broader
# ``USER_SUB`` used by config-flow / init tests so a snapshot diff that
# accidentally picks up an unscoped identifier is visually obvious.
SENSOR_TEST_SUB = "abrp-test-sub"


def build_vehicle_model_display(
    *,
    manufacturer: str = "Rivian",
    model: str = "R2",
    years: str = "2026",
    title: str = "Standard Long Range RWD",
    start_year: int | None = 2026,
    end_year: int | None = None,
) -> VehicleModelDisplay:
    """Build a typed VehicleModelDisplay for device-enrichment tests.

    Default fields compose (via ``aioabrp.VehicleModelDisplay.display_name``)
    to ``"Rivian R2 2026 Standard Long Range RWD"`` — the same string the old
    ``build_catalog_entry`` produced — so device-model assertions are
    unchanged.
    """
    return VehicleModelDisplay(
        manufacturer=manufacturer,
        model=model,
        years=years,
        title=title,
        start_year=start_year,
        end_year=end_year,
    )


def build_metric_value(
    value: float | ChargingState,
    *,
    time: datetime | None = None,
    provider: str | None = None,
) -> MetricValue:
    """Build a typed MetricValue (the unit of coordinator telemetry state)."""
    return MetricValue(value=value, time=time, provider=provider)


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
    minimal — no vehicles selected means no telemetry stream is spawned, so
    tests using this fixture don't need ``fake_stream``.
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
    """Patch the ``aioabrp.AbrpClient`` boundary with configurable mocks.

    Patches the three client methods on the library class object itself, so a
    single fixture covers every ``AbrpClient`` instance the integration builds:
    the setup-time client (which backs the garage fetch, the seed poll, and the
    SSE stream) and the config-flow client share the same class object, so
    patching the class methods patches all instances.

    - ``async_get_vehicles`` (autospec): returns the 2-vehicle
      ``mock_abrp_vehicles`` list.
    - ``async_get_vehicle_model_display`` (autospec): per-typecode configurable
      typed returns. Tests populate ``mock_abrp_client.display_responses`` keyed
      by typecode with either a ``VehicleModelDisplay`` (returned) or a
      ``BaseException`` (raised). Any typecode absent from the table raises
      ``AbrpApiError`` (404), so by default every vehicle's device card falls
      back to the raw typecode — matching the old empty-catalog default.
    - ``async_get_current_telemetry`` (the coordinator seed path, autospec):
      per-vehicle configurable typed returns. Tests populate
      ``mock_abrp_client.seed_responses`` keyed by vehicle id with either a
      ``Telemetry`` (returned) or a ``BaseException`` (raised),
      e.g.::

          mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry(
              soc=build_metric_value(42.0)
          )

      Any vehicle id absent from the table seeds an empty ``Telemetry()``.

    Autospec/self decision: all three patches use ``autospec=True``. Because
    autospec preserves the bound-method signature, the ``async_get_current_telemetry``
    side_effect receives ``self`` as its first positional arg (the real
    signature is ``(self, vehicle_id)``), so ``_seed`` is defined as
    ``_seed(self, vehicle_id)``.

    The ``async_get_vehicles`` mock is yielded as the primary handle, with
    ``.seed_responses`` attached to it for ergonomic per-vehicle seeding.
    """
    seed_responses: dict[int, Telemetry | BaseException] = {}

    async def _seed(self: Any, vehicle_id: int) -> Telemetry:
        outcome = seed_responses.get(vehicle_id, Telemetry())
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    display_responses: dict[str, VehicleModelDisplay | BaseException] = {}

    async def _display(self: Any, typecode: str) -> VehicleModelDisplay:
        outcome = display_responses.get(typecode)
        if outcome is None:
            raise AbrpApiError(f"HTTP 404 (no display fixture for {typecode})")
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    with (
        patch(
            "aioabrp.AbrpClient.async_get_vehicles",
            autospec=True,
            return_value=mock_abrp_vehicles,
        ) as mock_client,
        patch(
            "aioabrp.AbrpClient.async_get_vehicle_model_display",
            autospec=True,
            side_effect=_display,
        ),
        patch(
            "aioabrp.AbrpClient.async_get_current_telemetry",
            autospec=True,
            side_effect=_seed,
        ),
    ):
        mock_client.seed_responses = seed_responses
        mock_client.display_responses = display_responses
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


class _StreamDriver:
    """Test handle for driving a faked ``TelemetryStream`` synchronously."""

    def __init__(self, cls: Any) -> None:
        """Wrap the per-test fake stream class so the driver can find it."""
        self._cls = cls

    @property
    def stream(self) -> Any:
        """The most recently constructed fake stream (None before setup)."""
        return self._cls.instances[-1] if self._cls.instances else None

    def fire_frame(self, vehicle_id: int, telemetry: Telemetry) -> None:
        """Invoke the coordinator's on_update with a typed Telemetry frame."""
        assert self.stream is not None, (
            "fire_frame called before TelemetryStream construction"
        )
        self.stream.on_update(vehicle_id, telemetry)

    def fire_connection(self, event: ConnectionEvent) -> None:
        """Invoke the coordinator's on_connection_change with a transition."""
        assert self.stream is not None, (
            "fire_connection called before TelemetryStream construction"
        )
        self.stream.on_connection_change(event)


@pytest.fixture(name="fake_stream")
def fake_stream() -> Generator[_StreamDriver]:
    """Patch the integration's TelemetryStream with a synchronous test driver.

    Captures the constructor-injected on_update / on_connection_change
    callbacks and exposes fire_frame / fire_connection so tests drive
    push telemetry deterministically without a real SSE consumer.

    The fake stream class is defined inside the fixture so each test gets a
    fresh class with its own ``instances`` list — no cross-test leakage.
    """

    class _FakeTelemetryStream:
        """Test double for aioabrp.TelemetryStream.

        Captures the constructor-injected coordinator callbacks so a test can
        drive frames / connection transitions synchronously via the fixture's
        driver, instead of running a real SSE consumer. start()/stop() are
        awaitable no-ops that record their call for lifecycle assertions.
        """

        instances: list[Any] = []

        def __init__(
            self,
            websession: Any,
            api_key: str,
            auth: Any,
            vehicle_ids: list[int],
            on_update: Any,
            on_connection_change: Any,
            *,
            name: str | None = None,
            backoff: Any = (5.0, 10.0, 30.0, 60.0),
            watchdog_seconds: float = 300.0,
            seed: dict[int, Telemetry] | None = None,
        ) -> None:
            """Record the injected callbacks and register this instance."""
            self.vehicle_ids = list(vehicle_ids)
            self.on_update = on_update
            self.on_connection_change = on_connection_change
            self.name = name
            self.seed = seed
            self.started = False
            self.stopped = False
            _FakeTelemetryStream.instances.append(self)

        async def start(self) -> None:
            """Awaitable no-op that records the start call."""
            self.started = True

        async def stop(self) -> None:
            """Awaitable no-op that records the stop call."""
            self.stopped = True

    with patch(
        "homeassistant.components.abetterrouteplanner.TelemetryStream",
        _FakeTelemetryStream,
    ):
        yield _StreamDriver(_FakeTelemetryStream)
