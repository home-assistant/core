"""Tests for the A Better Routeplanner actions."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpScopeError,
    ChargingState,
    Location,
    TelemetryPoint,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.abrp.const import DOMAIN
from homeassistant.components.abrp.services import SERVICE_SEND_TELEMETRY
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import MOCK_VEHICLE_ID

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


@pytest.fixture(name="mock_send_telemetry")
def mock_send_telemetry_fixture() -> Generator[AsyncMock]:
    """Patch the telemetry write at the aioabrp boundary."""
    with patch("aioabrp.AbrpClient.async_send_telemetry", autospec=True) as mock_send:
        yield mock_send


@pytest.fixture(name="vehicle_device_id")
async def vehicle_device_id_fixture(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: AsyncMock,
) -> str:
    """Set up the integration and return the device id of the first vehicle."""
    await setup_integration(hass, config_entry_with_vehicles)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{config_entry_with_vehicles.unique_id}_{MOCK_VEHICLE_ID}"),
        config_entry_with_vehicles.entry_id,
    )
    assert device is not None
    return device.id


async def _send(hass: HomeAssistant, data: dict[str, Any]) -> None:
    await hass.services.async_call(DOMAIN, SERVICE_SEND_TELEMETRY, data, blocking=True)


@pytest.mark.freeze_time(NOW)
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"soc": 72}, {"soc_frac": 0.72}),
        ({"power": -7.2}, {"power_w": -7200.0}),
        ({"odometer": 12345}, {"odometer_m": 12345000.0}),
        ({"estimated_range": 310}, {"estimated_battery_range_m": 310000.0}),
        ({"battery_temperature": 18.5}, {"battery_temperature_c": 18.5}),
        (
            {"charging_state": "charging_ac"},
            {"charging_state": ChargingState.CHARGING_AC},
        ),
        (
            {"location": {"latitude": 59.3293, "longitude": 18.0686}},
            {"location": Location(lat=59.3293, lon=18.0686)},
        ),
        (
            {"time": "2026-11-09T10:30:00+01:00", "soc": 72},
            {"time": datetime(2026, 11, 9, 9, 30, tzinfo=UTC), "soc_frac": 0.72},
        ),
    ],
    ids=lambda case: next(iter(case)),
)
async def test_send_telemetry(
    hass: HomeAssistant,
    vehicle_device_id: str,
    mock_send_telemetry: AsyncMock,
    data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Each field is converted to its wire unit; time defaults to now."""
    await _send(hass, {"vehicle": vehicle_device_id, **data})

    mock_send_telemetry.assert_awaited_once()
    _, vehicle_id, point = mock_send_telemetry.await_args.args
    assert vehicle_id == MOCK_VEHICLE_ID
    assert point == TelemetryPoint(
        **{"provider": "HOME_ASSISTANT", "time": NOW, **expected}
    )


async def test_send_telemetry_vehicle_not_in_garage(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    vehicle_device_id: str,
    mock_send_telemetry: AsyncMock,
) -> None:
    """A device of the entry whose vehicle left the garage is rejected."""
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry_with_vehicles.entry_id,
        identifiers={(DOMAIN, f"{config_entry_with_vehicles.unique_id}_999")},
        name="Sold vehicle",
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _send(hass, {"vehicle": device.id, "soc": 50})

    assert exc_info.value.translation_key == "vehicle_not_in_garage"
    assert exc_info.value.translation_placeholders == {"vehicle": "Sold vehicle"}
    mock_send_telemetry.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "translation_key", "reauth_flows"),
    [
        pytest.param(
            AbrpScopeError("HTTP 403: insufficient_scope", scope="tlm:write"),
            "telemetry_write_not_granted",
            1,
            id="missing_scope",
        ),
        pytest.param(
            AbrpAuthError("HTTP 401"), "abrp_session_invalid", 1, id="auth_error"
        ),
        pytest.param(
            AbrpApiError("HTTP 500"), "send_telemetry_failed", 0, id="api_error"
        ),
    ],
)
async def test_send_telemetry_errors(
    hass: HomeAssistant,
    vehicle_device_id: str,
    mock_send_telemetry: AsyncMock,
    error: Exception,
    translation_key: str,
    reauth_flows: int,
) -> None:
    """Send failures raise a translated error; auth failures start a reauth."""
    mock_send_telemetry.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await _send(hass, {"vehicle": vehicle_device_id, "soc": 50})
    await hass.async_block_till_done()

    assert exc_info.value.translation_key == translation_key
    flows = hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, match_context={"source": SOURCE_REAUTH}
    )
    assert len(flows) == reauth_flows
