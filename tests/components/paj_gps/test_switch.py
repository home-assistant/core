"""Tests for PAJ GPS alert switch platform."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pajgps_api.models.device import Device
from pajgps_api.models.trackpoint import TrackPoint
from pajgps_api.pajgps_api_error import PajGpsApiError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.paj_gps.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "switch.device_1_sos_alert"

ALL_ALERTS_SUPPORTED = {
    "alarm_erschuetterung": 1,
    "alarm_batteriestand": 1,
    "alarm_sos": 1,
    "alarm_geschwindigkeit": 1,
    "alarm_stromunterbrechung": 1,
    "alarm_zuendalarm": 1,
    "alarm_drop": 1,
    "alarm_volt": 1,
}


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
                "device_models": [ALL_ALERTS_SUPPORTED],
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
    freezer: FrozenDateTimeFactory,
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

    mock_paj_gps_api_with_alerts.get_devices.reset_mock()
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_paj_gps_api_with_alerts.get_devices.assert_awaited_once()


async def test_alert_switches_created_once_device_data_completes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that switches are created on a later refresh once device data is complete."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.async_all(SWITCH_DOMAIN) == []

    mock_paj_gps_api.get_devices.return_value = [
        Device(
            **{
                **await async_load_json_object_fixture(hass, "device.json", DOMAIN),
                "device_models": [ALL_ALERTS_SUPPORTED],
            }
        )
    ]
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert {state.entity_id for state in hass.states.async_all(SWITCH_DOMAIN)} == {
        "switch.device_1_battery_alert",
        "switch.device_1_drop_alert",
        "switch.device_1_ignition_alert",
        "switch.device_1_power_cut_off_alert",
        "switch.device_1_shock_alert",
        "switch.device_1_sos_alert",
        "switch.device_1_speed_alert",
        "switch.device_1_voltage_alert",
    }


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"device_models": []}, id="no_device_models"),
        pytest.param({"device_models": [{"alarm_sos": 0}]}, id="model_flag_disabled"),
        pytest.param(
            {"alarmsos": None, "device_models": [ALL_ALERTS_SUPPORTED]},
            id="alarm_field_missing",
        ),
    ],
)
async def test_alert_switch_not_created_when_unsupported(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    overrides: dict[str, object],
) -> None:
    """Test that the SOS switch is skipped when the model or the device lacks it."""
    device_data = await async_load_json_object_fixture(hass, "device.json", DOMAIN)
    mock_paj_gps_api.get_devices.return_value = [Device(**{**device_data, **overrides})]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None


async def test_toggle_not_overwritten_by_in_flight_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_paj_gps_api_with_alerts: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a refresh started before a toggle does not revert the switch."""
    mock_paj_gps_api_with_alerts.get_devices.return_value[0].alarmsos = 0
    mock_paj_gps_api_with_alerts.update_device.return_value = Device(
        **{
            **await async_load_json_object_fixture(hass, "device.json", DOMAIN),
            "alarmsos": 1,
        }
    )
    await setup_integration(hass, mock_config_entry)

    refresh_started = asyncio.Event()
    release_refresh = asyncio.Event()

    async def blocked_positions(device_ids: list[int]) -> list[TrackPoint]:
        """Hold the refresh inside the coordinator lock until released."""
        refresh_started.set()
        await release_refresh.wait()
        trackpoint = await async_load_json_object_fixture(
            hass, "trackpoint.json", DOMAIN
        )
        return [TrackPoint(**trackpoint)]

    mock_paj_gps_api_with_alerts.get_all_last_positions.side_effect = blocked_positions
    coordinator = mock_config_entry.runtime_data
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await refresh_started.wait()

    toggle_task = hass.async_create_task(coordinator.async_set_alert(1, "alarmsos", 1))
    await asyncio.sleep(0)
    mock_paj_gps_api_with_alerts.update_device.assert_not_awaited()

    release_refresh.set()
    await toggle_task
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_alert_switch_unknown_when_field_missing_after_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_paj_gps_api_with_alerts: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the switch reports unknown once the device stops reporting the alert."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    mock_paj_gps_api_with_alerts.get_devices.return_value[0].alarmsos = None
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_toggle_keeps_polling_deadline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_paj_gps_api_with_alerts: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a toggle does not postpone the next scheduled device refresh."""
    mock_paj_gps_api_with_alerts.get_devices.return_value[0].alarmsos = 0
    mock_paj_gps_api_with_alerts.update_device.return_value = Device(
        **{
            **await async_load_json_object_fixture(hass, "device.json", DOMAIN),
            "alarmsos": 1,
        }
    )
    await setup_integration(hass, mock_config_entry)
    mock_paj_gps_api_with_alerts.get_devices.reset_mock()

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL - 5))
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_paj_gps_api_with_alerts.get_devices.assert_awaited_once()
