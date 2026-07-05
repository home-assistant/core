"""Test the nx584 integration setup."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from homeassistant.components.nx584.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_DATA = {CONF_HOST: "1.1.1.1", CONF_PORT: 5007}


@pytest.fixture(name="nx584_client")
def nx584_client_fixture():
    """Mock the nx584 client used by the config entry."""
    with patch("homeassistant.components.nx584.client.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.list_zones.return_value = []
        mock_client.list_partitions.return_value = [
            {"armed": False, "condition_flags": []}
        ]
        mock_client.get_version.return_value = "1.1"
        yield mock_client


@pytest.fixture(name="mock_config_entry")
def mock_config_entry_fixture() -> MockConfigEntry:
    """Return a fake nx584 config entry."""
    return MockConfigEntry(domain=DOMAIN, data=TEST_DATA)


async def test_setup_entry(
    hass: HomeAssistant, nx584_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a successful setup entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    nx584_client.list_zones.assert_called()


async def test_setup_entry_not_ready(
    hass: HomeAssistant, nx584_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when the panel can't be reached."""
    nx584_client.list_zones.side_effect = requests.exceptions.ConnectionError

    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, nx584_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
