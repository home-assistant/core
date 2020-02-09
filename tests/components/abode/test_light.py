"""Test for the Abode light device."""
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, LIGHT_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("light.living_room_lamp")
    assert entry.unique_id == "741385f4388b2637df4c6b398fe50581"


async def test_attributes(hass, requests_mock):
    """Test the light attributes are correct."""
    await setup_platform(hass, LIGHT_DOMAIN)

    state = hass.states.get("light.living_room_lamp")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 204
    assert state.attributes.get("rgb_color") == (0, 63, 255)
    assert state.attributes.get("color_temp") == 280
    assert state.attributes.get("device_id") == "ZB:db5b1a"
    assert not state.attributes.get("battery_low")
    assert not state.attributes.get("no_response")
    assert state.attributes.get("device_type") == "RGB Dimmer"
    assert state.attributes.get("friendly_name") == "Living Room Lamp"
    assert state.attributes.get("supported_features") == 19


async def test_switch_off(hass, requests_mock):
    """Test the light can be turned off."""
    await setup_platform(hass, LIGHT_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/control/light/ZB:db5b1a", text="",
    )

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.living_room_lamp"}
    )
    await hass.async_block_till_done()


async def test_switch_on(hass, requests_mock):
    """Test the light can be turned on."""
    await setup_platform(hass, LIGHT_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/control/light/ZB:db5b1a", text="",
    )

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.living_room_lamp"}
    )
    await hass.async_block_till_done()


async def test_set_brightness(hass, requests_mock):
    """Test the brightness can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/control/light/ZB:db5b1a", text="",
    )

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.living_room_lamp", "brightness": 100},
    )
    await hass.async_block_till_done()


async def test_set_color(hass, requests_mock):
    """Test the color can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/control/light/ZB:db5b1a", text="",
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_lamp", "rgb_color": [200, 100, 50]},
    )
    await hass.async_block_till_done()

    # Test color temp
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.living_room_lamp", "kelvin": 3000},
    )
    await hass.async_block_till_done()
