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
