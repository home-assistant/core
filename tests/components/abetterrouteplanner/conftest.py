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

from homeassistant.components.abetterrouteplanner.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

USER_SUB = "user-sub-12345"
REDIRECT_URI = "https://example.com/auth/external/callback"

MOCK_VEHICLE_ID = 941349991303
MOCK_VEHICLE_NAME = "Rivian R2 2027 Standard Long Range"
MOCK_VEHICLE_MODEL = "rivian:r2:26:ncma91:rwd:w21"
MOCK_PAINT = "WHITE"

MOCK_VEHICLE_ID_2 = 524289123456
MOCK_VEHICLE_NAME_2 = "Rivian R1S 2024 Quad Max"
MOCK_VEHICLE_MODEL_2 = "rivian:r1s:24:max:tri:w22"
MOCK_PAINT_2 = "BLACK"

# Distinct from ``USER_SUB`` so a snapshot picking up the wrong one is obvious.
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
    """Build a typed VehicleModelDisplay for device-enrichment tests."""
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
    """Build a fake JWT id_token with the given ``sub`` (and optional ``email``)."""
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
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
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
    """Default 2-vehicle garage returned by the patched ``AbrpClient``."""
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
    """Patch the ``aioabrp.AbrpClient`` boundary with configurable mocks."""
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
    ):
        mock_client.display_responses = display_responses
        yield mock_client


@pytest.fixture(name="config_entry_with_vehicles")
def mock_config_entry_with_vehicles(
    token_entry: dict[str, Any],
) -> MockConfigEntry:
    """Return a config entry scoped to the sensor tests' OIDC subject."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
        },
    )


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
    """Patch the integration's TelemetryStream with a synchronous test driver."""

    class _FakeTelemetryStream:
        """Test double for aioabrp.TelemetryStream."""

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
