"""Fixtures for Roku integration tests."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

import pytest
from rokuecp import Device as RokuDevice

from homeassistant.components.roku.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


def app_icon_url(*args, **kwargs):
    """Get the URL to the application icon."""
    app_id = args[0]
    return f"http://192.168.1.160:8060/query/icon/{app_id}"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Roku",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.160"},
        unique_id="1GU48T017973",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.roku.async_setup_entry", return_value=True):
        yield


@pytest.fixture
async def mock_device(
    request: pytest.FixtureRequest,
) -> RokuDevice:
    """Return the mocked roku device."""
    fixture: str = "roku/roku3.json"
    if hasattr(request, "param") and request.param:
        fixture = request.param

    return RokuDevice(json.loads(load_fixture(fixture)))


@pytest.fixture
def mock_roku_config_flow(mock_device: RokuDevice) -> Generator[MagicMock]:
    """Return a mocked Roku client."""

    with patch(
        "homeassistant.components.roku.config_flow.Roku", autospec=True
    ) as roku_mock:
        client = roku_mock.return_value
        client.app_icon_url.side_effect = app_icon_url
        client.update.return_value = mock_device
        yield client


@pytest.fixture
def mock_roku(mock_device: RokuDevice) -> Generator[MagicMock]:
    """Return a mocked Roku client."""

    with patch(
        "homeassistant.components.roku.coordinator.Roku", autospec=True
    ) as roku_mock:
        client = roku_mock.return_value
        client.app_icon_url.side_effect = app_icon_url
        client.update.return_value = mock_device
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: RokuDevice,
    mock_roku: MagicMock,
) -> MockConfigEntry:
    """Set up the Roku integration for testing."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id=mock_device.info.serial_number
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
