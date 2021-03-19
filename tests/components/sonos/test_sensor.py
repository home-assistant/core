"""Tests for the Sonos battery sensor platform."""
from pysonos.exceptions import NotSupportedException

from homeassistant.components.sonos import DOMAIN
from homeassistant.setup import async_setup_component


async def setup_platform(hass, config_entry, config):
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_entity_registry_unsupported(hass, config_entry, config, soco):
    """Test sonos device without battery registered in the device registry."""
    soco.get_battery_info.side_effect = NotSupportedException

    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    assert "media_player.zone_a" in entity_registry.entities
    assert "sensor.zone_a_battery" not in entity_registry.entities


async def test_entity_registry_supported(hass, config_entry, config, soco):
    """Test sonos device with battery registered in the device registry."""
    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    assert "media_player.zone_a" in entity_registry.entities
    assert "sensor.zone_a_battery" in entity_registry.entities


async def test_battery_missing_attributes(hass, config_entry, config, soco):
    """Test sonos device with unknown battery state."""
    soco.get_battery_info.return_value = {}

    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    battery = entity_registry.entities["sensor.zone_a_battery"]
    battery_state = hass.states.get(battery.entity_id)

    # confirm initial state from conftest
    assert battery_state.state == "unknown"
    assert battery_state.attributes.get("unit_of_measurement") == "%"
    assert battery_state.attributes.get("icon") == "mdi:battery-alert"
    assert not battery_state.attributes.get("charging")
    assert battery_state.attributes.get("power_source") == "unknown"


async def test_battery_attributes(hass, config_entry, config, soco):
    """Test sonos device with battery state."""
    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    battery = entity_registry.entities["sensor.zone_a_battery"]
    battery_state = hass.states.get(battery.entity_id)

    # confirm initial state from conftest
    assert battery_state.state == "100"
    assert battery_state.attributes.get("unit_of_measurement") == "%"
    assert battery_state.attributes.get("icon") == "mdi:battery-charging-100"
    assert battery_state.attributes.get("charging")
    assert battery_state.attributes.get("power_source") == "SONOS_CHARGING_RING"
