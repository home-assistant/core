"""Tests for the Marstek sensor platform."""

from dataclasses import replace
from unittest.mock import MagicMock

from aiomarstek import MarstekDeviceStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE_STATUS

from tests.common import MockConfigEntry, snapshot_platform

BATTERY_LEVEL_ENTITY_ID = "sensor.marstek_venuse_3_0_v1_battery_level"
BATTERY_POWER_ENTITY_ID = "sensor.marstek_venuse_3_0_v1_battery_power"
BATTERY_STATUS_ENTITY_ID = "sensor.marstek_venuse_3_0_v1_battery_status"
DEVICE_MODE_ENTITY_ID = "sensor.marstek_venuse_3_0_v1_device_mode"
PV1_POWER_ENTITY_ID = "sensor.marstek_venuse_3_0_v1_pv1_power"
PV1_STATE_ENTITY_ID = "sensor.marstek_venuse_3_0_v1_pv1_state"
PV1_VOLTAGE_ENTITY_ID = "sensor.marstek_venuse_3_0_v1_pv1_voltage"
PV2_POWER_ENTITY_ID = "sensor.marstek_venuse_3_0_v1_pv2_power"


def _get_state(hass: HomeAssistant, entity_id: str) -> State:
    """Return the state for an entity."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_setup_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor platform setup."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_polling_paused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test coordinator respects polling pause."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.is_polling_paused.return_value = True

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    mock_udp_client.get_device_status.assert_not_awaited()


async def test_polling_failure_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test polling failures make the sensor unavailable and then recover."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_udp_client.get_device_status.side_effect = [
        OSError("network down"),
        MOCK_DEVICE_STATUS,
    ]

    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _get_state(hass, BATTERY_LEVEL_ENTITY_ID).state == STATE_UNAVAILABLE

    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _get_state(hass, BATTERY_LEVEL_ENTITY_ID).state == "85"


async def test_missing_sensor_fields_do_not_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test missing device status fields are not reported as fallback values."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_status.side_effect = None
    mock_udp_client.get_device_status.return_value = MarstekDeviceStatus(
        device_ip="192.168.1.100",
        battery_power=1300,
        pv1_power=500,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _get_state(hass, BATTERY_LEVEL_ENTITY_ID).state == STATE_UNKNOWN
    assert _get_state(hass, DEVICE_MODE_ENTITY_ID).state == STATE_UNKNOWN
    assert _get_state(hass, BATTERY_STATUS_ENTITY_ID).state == STATE_UNKNOWN
    assert _get_state(hass, PV1_POWER_ENTITY_ID).state == "500"
    assert _get_state(hass, PV1_VOLTAGE_ENTITY_ID).state == STATE_UNKNOWN
    assert _get_state(hass, PV2_POWER_ENTITY_ID).state == STATE_UNKNOWN


async def test_sensor_uses_normalized_status_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test sensor values are read directly from the library status model."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_status.return_value = replace(
        MOCK_DEVICE_STATUS,
        device_mode="auto",
        battery_status="selling",
        pv1_state="standby",
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _get_state(hass, DEVICE_MODE_ENTITY_ID).state == "auto"
    assert _get_state(hass, BATTERY_STATUS_ENTITY_ID).state == "selling"
    assert _get_state(hass, PV1_STATE_ENTITY_ID).state == "standby"
