"""Test the default_config init."""

from unittest.mock import patch

import pytest

from homeassistant import bootstrap
from homeassistant.components.default_config import DOMAIN
from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def mock_ssdp():
    """Mock ssdp."""
    with (
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch("homeassistant.components.ssdp.Server.async_start"),
        patch("homeassistant.components.ssdp.Server.async_stop"),
    ):
        yield


@pytest.fixture(autouse=True)
def recorder_url_mock():
    """Mock recorder url."""
    with patch("homeassistant.components.recorder.DEFAULT_URL", "sqlite://"):
        yield


@pytest.mark.usefixtures("mock_bluetooth", "mock_zeroconf", "socket_enabled")
async def test_setup(hass: HomeAssistant) -> None:
    """Test setup."""
    recorder_helper.async_initialize_recorder(hass)
    # default_config needs the homeassistant integration, assert it will be
    # automatically setup by bootstrap and set it up manually for this test
    assert HOMEASSISTANT_DOMAIN in bootstrap.CORE_INTEGRATIONS
    assert await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {"foo": "bar"})

    assert await async_setup_component(hass, DOMAIN, {"foo": "bar"})
