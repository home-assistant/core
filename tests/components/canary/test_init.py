"""The tests for the Canary component."""
from homeassistant.components.canary import DOMAIN
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


async def test_setup_with_valid_config(hass, canary) -> None:
    """Test setup with valid YAML."""
    assert await async_setup_component(hass, "persistent_notification", {})
    config = {DOMAIN: {"username": "foo@bar.org", "password": "bar"}}

    with patch(
        "homeassistant.components.canary.alarm_control_panel.setup_platform",
        return_value=True,
    ), patch(
        "homeassistant.components.canary.camera.setup_platform",
        return_value=True,
    ), patch(
        "homeassistant.components.canary.sensor.setup_platform",
        return_value=True,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
