"""Fixtures for the A Better Routeplanner integration tests."""

import base64
from collections.abc import Generator
from http import HTTPStatus
import inspect
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aioabrp import (
    AbrpApiError,
    AbrpVehicle,
    AbstractAuth,
    ChargingState,
    ConnectionEvent,
    MetricValue,
    Telemetry,
    TelemetryStream,
    VehicleModelDisplay,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.abrp.const import DOMAIN
from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

CLIENT_ID = "client-id"
CLIENT_SECRET = "client-secret"
USER_SUB = "user-sub-12345"
REDIRECT_URI = "https://example.com/auth/external/callback"

MOCK_VEHICLE_ID = 123456789012
MOCK_VEHICLE_NAME = "Rivian R2 2027 Standard Long Range"
MOCK_VEHICLE_MODEL = "rivian:r2:26:ncma91:rwd:w21"
MOCK_PAINT = "WHITE"

MOCK_VEHICLE_ID_2 = 123456789013
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


def build_metric_value(value: float | ChargingState) -> MetricValue:
    """Build a typed MetricValue (the unit of coordinator telemetry state)."""
    return MetricValue(value=value, time=None, provider=None)


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


def build_id_token(
    sub: str = USER_SUB, *, email: str | None = None, name: str | None = None
) -> str:
    """Build a fake JWT id_token with the given ``sub`` and optional claims."""
    payload_dict: dict[str, Any] = {"sub": sub}
    if email is not None:
        payload_dict["email"] = email
    if name is not None:
        payload_dict["name"] = name
    payload = json.dumps(payload_dict).encode()
    payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    return f"header.{payload_b64}.signature"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET)
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the OAuth token expiration time."""
    return time.time() + 86400


@pytest.fixture(name="token_entry")
def mock_token_entry(expires_at: float) -> dict[str, Any]:
    """Fixture for OAuth ``token`` data for a ConfigEntry."""
    return {
        "access_token": "mock-access-token",
        "refresh_token": "mock-refresh-token",
        "token_type": "Bearer",
        "expires_at": expires_at,
        "id_token": build_id_token(),
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
        "homeassistant.components.abrp.async_setup_entry",
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


def fire_frame(
    mock_telemetry_stream: MagicMock, vehicle_id: int, telemetry: Telemetry
) -> None:
    """Deliver a telemetry frame through the stream's on_update callback."""
    assert mock_telemetry_stream.call_args is not None, "no stream was constructed"
    mock_telemetry_stream.call_args.kwargs["on_update"](vehicle_id, telemetry)


def fire_connection(mock_telemetry_stream: MagicMock, event: ConnectionEvent) -> None:
    """Deliver a connection transition through on_connection_change."""
    assert mock_telemetry_stream.call_args is not None, "no stream was constructed"
    mock_telemetry_stream.call_args.kwargs["on_connection_change"](event)


def stream_auth(mock_telemetry_stream: MagicMock) -> AbstractAuth:
    """Return the auth the integration handed to the telemetry stream."""
    assert mock_telemetry_stream.call_args is not None, "no stream was constructed"
    call = mock_telemetry_stream.call_args
    return (
        inspect.signature(TelemetryStream)
        .bind(*call.args, **call.kwargs)
        .arguments["auth"]
    )


@pytest.fixture
def mock_telemetry_stream() -> Generator[MagicMock]:
    """Patch the integration's TelemetryStream with an autospec mock."""
    with patch(
        "homeassistant.components.abrp.TelemetryStream",
        autospec=True,
    ) as mock_stream:
        yield mock_stream
