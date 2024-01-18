"""Tests for the Flexit Nordic (BACnet) sensor entities."""
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry
from tests.components.flexit_bacnet import setup_with_selected_platforms


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.device_name_air_filter_operating_time",
        "sensor.device_name_outside_air_temperature",
        "sensor.device_name_supply_air_temperature",
        "sensor.device_name_exhaust_air_temperature",
        "sensor.device_name_extract_air_temperature",
        "sensor.device_name_room_temperature",
        "sensor.device_name_fireplace_ventilation_remaining_duration",
        "sensor.device_name_rapid_ventilation_remaining_duration",
        "sensor.device_name_supply_air_fan_control_signal",
        "sensor.device_name_supply_air_fan_rpm",
        "sensor.device_name_exhaust_air_fan_control_signal",
        "sensor.device_name_exhaust_air_fan_rpm",
        "sensor.device_name_electric_heater_power",
        "sensor.device_name_air_filter_operating_time",
        "sensor.device_name_heat_exchanger_efficiency",
        "sensor.device_name_heat_exchanger_speed",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_flexit_bacnet: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test a Flexit (BACnet) sensor."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot
