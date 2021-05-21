"""Tests for the Sonos Alarm switch platform."""
from homeassistant.components.sonos import DOMAIN
from homeassistant.const import ATTR_TIME, STATE_ON
from homeassistant.setup import async_setup_component


async def setup_platform(hass, config_entry, config):
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_entity_registry(hass, config_entry, config, soco):
    """Test sonos device with alarm registered in the device registry."""
    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    assert "media_player.zone_a" in entity_registry.entities
    assert "switch.sonos_alarm_14" in entity_registry.entities


async def test_alarm_attributes(hass, config_entry, config, soco):
    """Test for correct sonos alarm state."""
    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    alarm = entity_registry.entities["switch.sonos_alarm_14"]
    alarm_state = hass.states.get(alarm.entity_id)
    assert alarm_state.state == STATE_ON
    assert alarm_state.attributes.get(ATTR_TIME) == "07:00:00"
