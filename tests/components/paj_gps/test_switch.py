"""Tests for PAJ GPS alert switch platform."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pajgps_api.models.device import Device
from pajgps_api.pajgps_api_error import PajGpsApiError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.paj_gps.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "switch.device_1_sos_alert"


@pytest.fixture(autouse=True)
def switch_only() -> Generator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.paj_gps.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.fixture
def mock_paj_gps_api_with_alerts(mock_paj_gps_api: AsyncMock) -> AsyncMock:
    """Override get_devices to return a device that supports all alert types."""
    mock_paj_gps_api.get_devices.return_value = [
        Device(
            **{
                **load_json_object_fixture("device.json", DOMAIN),
                "device_models": [
                    {
                        "alarm_erschuetterung": 1,
                        "alarm_batteriestand": 1,
                        "alarm_sos": 1,
                        "alarm_geschwindigkeit": 1,
                        "alarm_stromunterbrechung": 1,
                        "alarm_zuendalarm": 1,
                        "alarm_drop": 1,
                        "alarm_volt": 1,
                    }
                ],
            }
        )
    ]
    return mock_paj_gps_api


@pytest.mark.usefixtures("mock_paj_gps_api_with_alerts")
async def test_alert_switches_created_when_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that one switch is created per alert the device model supports."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_paj_gps_api")
async def test_alert_switches_not_created_without_model_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no alert switch is created when the device model supports no alerts."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_all(SWITCH_DOMAIN) == []


@pytest.mark.parametrize(
    ("service", "initial", "value", "expected_state"),
    [
        pytest.param(SERVICE_TURN_ON, 0, 1, STATE_ON, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, 1, 0, STATE_OFF, id="turn_off"),
    ],
)
async def test_toggle_alert(
    hass: HomeAssistant,
    mock_paj_gps_api_with_alerts: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    initial: int,
    value: int,
    expected_state: str,
) -> None:
    """Test that toggling the switch sends the update and reflects the returned state."""
    mock_paj_gps_api_with_alerts.get_devices.return_value[0].alarmsos = initial
    mock_paj_gps_api_with_alerts.update_device.return_value = Device(
        **{
            **await async_load_json_object_fixture(hass, "device.json", DOMAIN),
            "alarmsos": value,
        }
    )

    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_paj_gps_api_with_alerts.update_device.assert_awaited_once_with(
        1, alarmsos=value
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_toggle_alert_raises_on_api_error(
    hass: HomeAssistant,
    mock_paj_gps_api_with_alerts: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an API failure raises an error and keeps the previous state."""
    mock_paj_gps_api_with_alerts.get_devices.return_value[0].alarmsos = 0
    mock_paj_gps_api_with_alerts.update_device.side_effect = PajGpsApiError("boom")

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match="boom"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
