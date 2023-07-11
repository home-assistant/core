"""Test the default_config init."""
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(autouse=True)
def mock_ssdp():
    """Mock ssdp."""
    with patch("homeassistant.components.ssdp.Scanner.async_scan"), patch(
        "homeassistant.components.ssdp.Server.async_start"
    ), patch("homeassistant.components.ssdp.Server.async_stop"):
        yield


@pytest.fixture(autouse=True)
def recorder_url_mock():
    """Mock recorder url."""
    with patch("homeassistant.components.recorder.DEFAULT_URL", "sqlite://"):
        yield


async def test_setup(
    hass: HomeAssistant, mock_zeroconf: None, mock_get_source_ip, mock_bluetooth: None
) -> None:
    """Test setup."""
    recorder_helper.async_initialize_recorder(hass)
    assert await async_setup_component(hass, "default_config", {"foo": "bar"})
