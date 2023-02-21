"""Test ZHA API."""
from unittest.mock import patch

import pytest

from homeassistant.components.zha import api


@pytest.fixture(autouse=True)
def required_platform_only():
    """Only set up the required and required base platforms to speed up tests."""
    with patch("homeassistant.components.zha.PLATFORMS", ()):
        yield


async def test_async_get_network_settings_active(hass, setup_zha):
    """Test reading settings with an active ZHA installation."""
    await api.async_get_network_settings(hass)
    # TODO


async def test_async_get_network_settings_failure(hass):
    """Test reading settings with no ZHA config entries."""
    with pytest.raises(ValueError):
        await api.async_get_network_settings(hass)
