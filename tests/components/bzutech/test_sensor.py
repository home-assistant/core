"""Test sensors."""

from homeassistant.components.bzutech.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import USER_INPUT

from tests.common import MockConfigEntry


async def test_sensors(hass: HomeAssistant, bzutech) -> None:
    """Test adding sensor entities and states."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    config_entry.add_to_hass(hass)

    await hass.async_block_till_done()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    statetemperature = hass.states.get("sensor.19284_3_temperature")
    statehumidity = hass.states.get("sensor.19284_3_humidity")
    stateilluminance = hass.states.get("sensor.19284_3_illuminance")

    assert statetemperature
    assert statehumidity
    assert stateilluminance
