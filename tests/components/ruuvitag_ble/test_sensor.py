"""Test the Ruuvitag BLE sensors."""

from __future__ import annotations

import pytest

from homeassistant.components.ruuvitag_ble.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from .fixtures import CONFIGURED_NAME, CONFIGURED_PREFIX, RUUVITAG_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("enable_bluetooth")
async def test_sensors(hass: HomeAssistant) -> None:
    """Test the RuuviTag BLE sensors."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=RUUVITAG_SERVICE_INFO.address)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(
        hass,
        RUUVITAG_SERVICE_INFO,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) >= 4

    for sensor, value, unit, state_class in (
        ("temperature", "7.2", "°C", "measurement"),
        ("humidity", "61.84", "%", "measurement"),
        ("pressure", "1013.54", "hPa", "measurement"),
        ("voltage", "2395", "mV", "measurement"),
    ):
        state = hass.states.get(f"sensor.{CONFIGURED_PREFIX}_{sensor}")
        assert state is not None
        assert state.state == value
        name_lower = state.attributes[ATTR_FRIENDLY_NAME].lower()
        assert name_lower == f"{CONFIGURED_NAME} {sensor}".lower()
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit
        assert state.attributes[ATTR_STATE_CLASS] == state_class
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
