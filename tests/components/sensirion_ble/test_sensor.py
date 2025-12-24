"""Test the Sensirion BLE sensors."""

from __future__ import annotations

import pytest

from homeassistant.components.sensirion_ble.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from .fixtures import (
    CONFIGURED_NAME_MYCO2,
    CONFIGURED_NAME_SHT43,
    CONFIGURED_PREFIX_MYCO2,
    CONFIGURED_PREFIX_SHT43,
    SENSIRION_SERVICE_INFO_MYCO2,
    SENSIRION_SERVICE_INFO_SHT43,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    (
        "sensirion_service_info",
        "configured_prefix",
        "configured_name",
        "sensor_value_unit_state_class_list",
    ),
    [
        (
            SENSIRION_SERVICE_INFO_MYCO2,
            CONFIGURED_PREFIX_MYCO2,
            CONFIGURED_NAME_MYCO2,
            [
                ("carbon_dioxide", "724", "ppm", "measurement"),
            ],
        ),
        (
            SENSIRION_SERVICE_INFO_SHT43,
            CONFIGURED_PREFIX_SHT43,
            CONFIGURED_NAME_SHT43,
            [
                ("humidity", "45.75", "%", "measurement"),
                ("temperature", "21.47", "°C", "measurement"),
            ],
        ),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    sensirion_service_info,
    configured_prefix,
    configured_name,
    sensor_value_unit_state_class_list,
) -> None:
    """Test the Sensirion BLE sensors."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=sensirion_service_info.address)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(
        hass,
        sensirion_service_info,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) >= len(sensor_value_unit_state_class_list)

    for sensor, value, unit, state_class in sensor_value_unit_state_class_list:
        state = hass.states.get(f"sensor.{configured_prefix}_{sensor}")
        assert state is not None
        assert state.state == value
        name_lower = state.attributes[ATTR_FRIENDLY_NAME].lower()
        assert name_lower == f"{configured_name} {sensor}".lower().replace("_", " ")
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit
        assert state.attributes[ATTR_STATE_CLASS] == state_class
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
