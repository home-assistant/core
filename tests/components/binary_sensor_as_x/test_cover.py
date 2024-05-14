"""Tests for the Binary sensor as X Cover platform."""

from homeassistant.components.binary_sensor_as_x.config_flow import (
    BinarySensorAsXConfigFlowHandler,
)
from homeassistant.components.binary_sensor_as_x.const import CONF_TARGET_DOMAIN, DOMAIN
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_default_state(hass: HomeAssistant) -> None:
    """Test cover binary sensor default state."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "binary_sensor.test",
            CONF_TARGET_DOMAIN: Platform.COVER,
        },
        title="Bedroom Door",
        version=BinarySensorAsXConfigFlowHandler.VERSION,
        minor_version=BinarySensorAsXConfigFlowHandler.MINOR_VERSION,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.bedroom_door")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes["supported_features"] == 0


async def test_device_class(hass: HomeAssistant) -> None:
    """Test cover binary sensor default state."""
    hass.states.async_set("binary_sensor.test", "on", {"device_class": "door"})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "binary_sensor.test",
            CONF_TARGET_DOMAIN: Platform.COVER,
        },
        title="Bedroom Door",
        version=BinarySensorAsXConfigFlowHandler.VERSION,
        minor_version=BinarySensorAsXConfigFlowHandler.MINOR_VERSION,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.bedroom_door")
    assert state is not None
    assert state.state == "open"
    assert state.attributes["supported_features"] == 0
    assert state.attributes["device_class"] == "door"
