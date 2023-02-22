"""Test ZHA API."""
from unittest.mock import patch

import pytest

from homeassistant.components import zha
from homeassistant.components.zha import api


@pytest.fixture(autouse=True)
def required_platform_only():
    """Only set up the required and required base platforms to speed up tests."""
    with patch("homeassistant.components.zha.PLATFORMS", ()):
        yield


async def test_async_get_network_settings_active(hass, setup_zha):
    """Test reading settings with an active ZHA installation."""
    await setup_zha()

    api._get_gateway(hass)

    settings = await api.async_get_network_settings(hass)
    assert settings.network_info.channel == 15


async def test_async_get_network_settings_inactive(
    hass, setup_zha, zigpy_app_controller
):
    """Test reading settings with an inactive ZHA installation."""
    await setup_zha()

    gateway = api._get_gateway(hass)
    await zha.async_unload_entry(hass, gateway.config_entry)

    zigpy_app_controller.state.network_info.channel = 20

    with patch(
        "bellows.zigbee.application.ControllerApplication.__new__",
        return_value=zigpy_app_controller,
    ):
        settings = await api.async_get_network_settings(hass)

    assert len(zigpy_app_controller._load_db.mock_calls) == 1
    assert len(zigpy_app_controller.start_network.mock_calls) == 0

    assert settings.network_info.channel == 20


async def test_async_get_network_settings_failure(hass):
    """Test reading settings with no ZHA config entries and no database."""
    with pytest.raises(ValueError):
        await api.async_get_network_settings(hass)
