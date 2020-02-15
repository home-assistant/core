"""Tests for the Abode light device."""
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
        "https://my.goabode.com/api/v1/control/light/ZB:db5b1a",
        json={"id": "ZB:db5b1a", "status": "0"},
    )

    assert await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.living_room_lamp"}, blocking=True
    )
    await hass.async_block_till_done()
    # Manually call the callback
    device = hass.data["abode"].abode.get_device("ZB:db5b1a")
    # pylint: disable=W0212
    hass.data["abode"].abode.events._device_callbacks["ZB:db5b1a"][0](device)

    # state = hass.states.get("light.living_room_lamp")
    # assert state.state == "off"


async def test_switch_on(hass, requests_mock):
    """Test the light can be turned on."""
    await setup_platform(hass, LIGHT_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/control/light/ZB:db5b1a",
        json={"id": "ZB:db5b1a", "status": "1"},
    )

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.living_room_lamp"}, blocking=True
    )
    await hass.async_block_till_done()


async def test_set_brightness(hass, requests_mock):
    """Test the brightness can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/control/light/ZB:db5b1a",
        json={"id": "ZB:db5b1a", "level": "39"},
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_lamp", "brightness": 100},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_set_color(hass, requests_mock):
    """Test the color can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)
    requests_mock.put(
        "https://my.goabode.com/api/v1/control/light/ZB:db5b1a",
        json={"id": "ZB:db5b1a", "status": "1"},
    )

    requests_mock.post(
        "https://my.goabode.com/integrations/v1/devices/741385f4388b2637df4c6b398fe50581",
        json={
            "id": "741385f4388b2637df4c6b398fe50581",
            "idForPanel": "ZB:db5b1a",
            "name": "Living Room Lamp",
            "state": {
                "brightness": 68,
                "powerState": "ON",
                "color": {"hue": 240, "saturation": 100},
            },
            "dimLevel": 68,
            "colorMode": "hue",
            "hue": 240,
            "saturation": 100,
        },
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_lamp", "hs_color": [240, 100]},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Test color temp
    await setup_platform(hass, LIGHT_DOMAIN)
    requests_mock.post(
        "https://my.goabode.com/integrations/v1/devices/741385f4388b2637df4c6b398fe50581",
        json={
            "id": "741385f4388b2637df4c6b398fe50581",
            "idForPanel": "ZB:db5b1a",
            "name": "Living Room Lamp",
            "state": {
                "brightness": 68,
                "powerState": "ON",
                "colorTemperatureInKelvin": 3236,
            },
            "dimLevel": 68,
            "colorMode": "temp",
            "colorTemperature": 3236,
        },
    )

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.living_room_lamp", "color_temp": 309},
    )
    await hass.async_block_till_done()
