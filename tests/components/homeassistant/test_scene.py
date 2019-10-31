"""Test Home Assistant scenes."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component


async def test_reload_config_service(hass):
    """Test the reload config service."""
    assert await async_setup_component(hass, "scene", {})

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={"scene": {"name": "Hallo", "entities": {"light.kitchen": "on"}}},
    ), patch("homeassistant.config.find_config_file", return_value=""):
        await hass.services.async_call("scene", "reload", blocking=True)
        await hass.async_block_till_done()

    assert hass.states.get("scene.hallo") is not None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={"scene": {"name": "Bye", "entities": {"light.kitchen": "on"}}},
    ), patch("homeassistant.config.find_config_file", return_value=""):
        await hass.services.async_call("scene", "reload", blocking=True)
        await hass.async_block_till_done()

    assert hass.states.get("scene.hallo") is None
    assert hass.states.get("scene.bye") is not None


async def test_apply_service(hass):
    """Test the apply service."""
    assert await async_setup_component(hass, "scene", {})
    assert await async_setup_component(hass, "light", {"light": {"platform": "demo"}})

    assert await hass.services.async_call(
        "scene", "apply", {"entities": {"light.bed_light": "off"}}, blocking=True
    )

    assert hass.states.get("light.bed_light").state == "off"

    assert await hass.services.async_call(
        "scene",
        "apply",
        {"entities": {"light.bed_light": {"state": "on", "brightness": 50}}},
        blocking=True,
    )

    state = hass.states.get("light.bed_light")
    assert state.state == "on"
    assert state.attributes["brightness"] == 50
