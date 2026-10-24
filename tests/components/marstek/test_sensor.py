"""Tests for the Marstek sensor platform."""

from dataclasses import replace
from unittest.mock import MagicMock

from aiomarstek import MarstekDeviceStatus
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE_INFO, MOCK_DEVICE_STATUS, TEST_HOST

BATTERY_LEVEL_ENTITY_ID = "sensor.marstek_venusa_v1_battery_level"
BATTERY_POWER_ENTITY_ID = "sensor.marstek_venusa_v1_battery_power"
BATTERY_STATUS_ENTITY_ID = "sensor.marstek_venusa_v1_battery_status"
DEVICE_MODE_ENTITY_ID = "sensor.marstek_venusa_v1_device_mode"
PV1_POWER_ENTITY_ID = "sensor.marstek_venusa_v1_pv_input_1_power"
PV1_STATE_ENTITY_ID = "sensor.marstek_venusa_v1_pv_input_1_state"
PV1_VOLTAGE_ENTITY_ID = "sensor.marstek_venusa_v1_pv_input_1_voltage"
PV2_POWER_ENTITY_ID = "sensor.marstek_venusa_v1_pv_input_2_power"
TOTAL_PV_ENERGY_ENTITY_ID = "sensor.marstek_venusa_v1_lifetime_pv_energy"


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


async def test_polling_failure_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test polling failures make the sensor unavailable and then recover."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_udp_client.get_device_status.side_effect = [
        OSError("network down"),
        MOCK_DEVICE_STATUS,
    ]

    freezer.tick(mock_config_entry.runtime_data.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _get_state(hass, BATTERY_LEVEL_ENTITY_ID).state == STATE_UNAVAILABLE

    freezer.tick(mock_config_entry.runtime_data.update_interval)
    async_fire_time_changed(hass)
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
    assert _get_state(hass, TOTAL_PV_ENERGY_ENTITY_ID).state == STATE_UNKNOWN
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
    assert _get_state(hass, TOTAL_PV_ENERGY_ENTITY_ID).state == "2810"

    # PV-capable devices must request PV data from the library.
    mock_udp_client.get_device_status.assert_awaited_once_with(
        TEST_HOST, previous_data=None, include_pv=True
    )


async def test_non_pv_device_has_no_pv_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test that devices without PV inputs do not get PV sensors."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_info.return_value = replace(
        MOCK_DEVICE_INFO, device_type="VenusE 3.0"
    )
    hass.config_entries.async_update_entry(
        mock_config_entry,
        title="VenusE 3.0 v1 (192.168.1.100)",
        data={**mock_config_entry.data, "device_type": "VenusE 3.0"},
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = {
        e.unique_id: e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }

    # Non-PV devices should not have any PV-related entities.
    assert not any("pv" in uid for uid in entities)
    # But should still have the non-PV entities.
    assert any("battery_soc" in uid for uid in entities)
    assert any("device_mode" in uid for uid in entities)

    # Non-PV devices must not request PV data from the library.
    mock_udp_client.get_device_status.assert_awaited_once_with(
        TEST_HOST, previous_data=None, include_pv=False
    )
