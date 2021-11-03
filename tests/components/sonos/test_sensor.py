"""Tests for the Sonos battery sensor platform."""
from soco.exceptions import NotSupportedException

from homeassistant.components.sonos import DOMAIN
from homeassistant.components.sonos.binary_sensor import ATTR_BATTERY_POWER_SOURCE
from homeassistant.const import STATE_OFF, STATE_ON
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
    assert "binary_sensor.zone_a_power" not in entity_registry.entities


async def test_entity_registry_supported(hass, config_entry, config, soco):
    """Test sonos device with battery registered in the device registry."""
    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    assert "media_player.zone_a" in entity_registry.entities
    assert "sensor.zone_a_battery" in entity_registry.entities
    assert "binary_sensor.zone_a_power" in entity_registry.entities


async def test_battery_attributes(hass, config_entry, config, soco):
    """Test sonos device with battery state."""
    await setup_platform(hass, config_entry, config)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    battery = entity_registry.entities["sensor.zone_a_battery"]
    battery_state = hass.states.get(battery.entity_id)
    assert battery_state.state == "100"
    assert battery_state.attributes.get("unit_of_measurement") == "%"

    power = entity_registry.entities["binary_sensor.zone_a_power"]
    power_state = hass.states.get(power.entity_id)
    assert power_state.state == STATE_ON
    assert (
        power_state.attributes.get(ATTR_BATTERY_POWER_SOURCE) == "SONOS_CHARGING_RING"
    )


async def test_battery_on_S1(hass, config_entry, config, soco, battery_event):
    """Test battery state updates on a Sonos S1 device."""
    soco.get_battery_info.return_value = {}

    await setup_platform(hass, config_entry, config)

    subscription = soco.deviceProperties.subscribe.return_value
    sub_callback = subscription.callback

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    assert "sensor.zone_a_battery" not in entity_registry.entities
    assert "binary_sensor.zone_a_power" not in entity_registry.entities

    # Update the speaker with a callback event
    sub_callback(battery_event)
    await hass.async_block_till_done()

    battery = entity_registry.entities["sensor.zone_a_battery"]
    battery_state = hass.states.get(battery.entity_id)
    assert battery_state.state == "100"

    power = entity_registry.entities["binary_sensor.zone_a_power"]
    power_state = hass.states.get(power.entity_id)
    assert power_state.state == STATE_OFF
    assert power_state.attributes.get(ATTR_BATTERY_POWER_SOURCE) == "BATTERY"


async def test_device_payload_without_battery(
    hass, config_entry, config, soco, battery_event, caplog
):
    """Test device properties event update without battery info."""
    soco.get_battery_info.return_value = None

    await setup_platform(hass, config_entry, config)

    subscription = soco.deviceProperties.subscribe.return_value
    sub_callback = subscription.callback

    bad_payload = "BadKey:BadValue"
    battery_event.variables["more_info"] = bad_payload

    sub_callback(battery_event)
    await hass.async_block_till_done()

    assert bad_payload in caplog.text


async def test_device_payload_without_battery_and_ignored_keys(
    hass, config_entry, config, soco, battery_event, caplog
):
    """Test device properties event update without battery info and ignored keys."""
    soco.get_battery_info.return_value = None

    await setup_platform(hass, config_entry, config)

    subscription = soco.deviceProperties.subscribe.return_value
    sub_callback = subscription.callback

    ignored_payload = "SPID:InCeiling,TargetRoomName:Bouncy House"
    battery_event.variables["more_info"] = ignored_payload

    sub_callback(battery_event)
    await hass.async_block_till_done()

    assert ignored_payload not in caplog.text
