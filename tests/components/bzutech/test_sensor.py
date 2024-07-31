"""Test sensors."""

from homeassistant.components.bzutech.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import USER_INPUT

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant, bzutech, entity_registry: er.EntityRegistry
) -> None:
    """Test adding sensor entities and states."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    config_entry.add_to_hass(hass)

    await hass.async_block_till_done()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entrytemperature = entity_registry.async_get("sensor.mock_title_temperature")
    entryhumidity = entity_registry.async_get("sensor.mock_title_humidity")
    entryilluminance = entity_registry.async_get("sensor.mock_title_illuminance")

    assert entrytemperature
    assert entryhumidity
    assert entryilluminance

    assert entrytemperature.disabled is False
    assert entryhumidity.disabled is False
    assert entryilluminance.disabled is False

    statetemperature = hass.states.get("sensor.mock_title_temperature")
    statehumidity = hass.states.get("sensor.mock_title_humidity")
    stateilluminance = hass.states.get("sensor.mock_title_illuminance")

    assert statetemperature
    assert statehumidity
    assert stateilluminance
