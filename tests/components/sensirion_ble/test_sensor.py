"""Test the Sensirion BLE sensors."""

from __future__ import annotations

from homeassistant.components.sensirion_ble.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from .fixtures import CONFIGURED_NAME, CONFIGURED_PREFIX, SENSIRION_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors(enable_bluetooth: None, hass: HomeAssistant) -> None:
    """Test the Sensirion BLE sensors."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=SENSIRION_SERVICE_INFO.address)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(
        hass,
        SENSIRION_SERVICE_INFO,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) >= 3

    for sensor, value, unit, state_class in [
        ("carbon_dioxide", "724", "ppm", "measurement"),
        ("humidity", "27.8", "%", "measurement"),
        ("temperature", "20.1", "°C", "measurement"),
    ]:
        state = hass.states.get(f"sensor.{CONFIGURED_PREFIX}_{sensor}")
        assert state is not None
        assert state.state == value
        name_lower = state.attributes[ATTR_FRIENDLY_NAME].lower()
        assert name_lower == f"{CONFIGURED_NAME} {sensor}".lower().replace("_", " ")
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit
        assert state.attributes[ATTR_STATE_CLASS] == state_class
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
