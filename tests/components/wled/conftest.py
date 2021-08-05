"""Fixtures for WLED integration tests."""
import json
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from wled import Device as WLEDDevice

from homeassistant.components.wled.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
async def mock_persistent_notification(hass: HomeAssistant) -> None:
    """Set up component for persistent notifications."""
    await async_setup_component(hass, "persistent_notification", {})


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.123", CONF_MAC: "aabbccddeeff"},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.wled.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_wled_config_flow(
    request: pytest.FixtureRequest,
) -> Generator[None, MagicMock, None]:
    """Return a mocked WLED client."""
    with patch(
        "homeassistant.components.wled.config_flow.WLED", autospec=True
    ) as wled_mock:
        wled = wled_mock.return_value
        wled.update.return_value = WLEDDevice(json.loads(load_fixture("wled/rgb.json")))
        yield wled


@pytest.fixture
def mock_wled(request: pytest.FixtureRequest) -> Generator[None, MagicMock, None]:
    """Return a mocked WLED client."""
    fixture: str = "wled/rgb.json"
    if hasattr(request, "param") and request.param:
        fixture = request.param

    device = WLEDDevice(json.loads(load_fixture(fixture)))
    with patch(
        "homeassistant.components.wled.coordinator.WLED", autospec=True
    ) as wled_mock:
        wled = wled_mock.return_value
        wled.update.return_value = device
        wled.connected = False
        yield wled


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wled: MagicMock
) -> MockConfigEntry:
    """Set up the WLED integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
