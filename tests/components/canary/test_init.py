"""The tests for the Canary component."""
import pytest
from requests import ConnectTimeout, HTTPError

from homeassistant.components.canary import DOMAIN
from homeassistant.exceptions import PlatformNotReady
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


async def test_setup_with_valid_config(hass, canary) -> None:
    """Test setup with valid YAML."""
    await async_setup_component(hass, "persistent_notification", {})
    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}

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


async def test_setup_with_http_error(hass, canary) -> None:
    """Test setup with HTTP error."""
    await async_setup_component(hass, "persistent_notification", {})
    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}

    canary.side_effect = HTTPError()

    assert not await async_setup_component(hass, DOMAIN, config)


async def test_setup_with_timeout_error(hass, canary) -> None:
    """Test setup with timeout error."""
    await async_setup_component(hass, "persistent_notification", {})
    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}

    canary.side_effect = ConnectTimeout()

    with pytest.raises(PlatformNotReady):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
