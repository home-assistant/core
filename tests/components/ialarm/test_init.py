"""Test the Antifurto365 iAlarm init."""
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from homeassistant.components.ialarm.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture(name="ialarm_api")
def ialarm_api_fixture():
    """Set up IAlarm API fixture."""
    with patch("homeassistant.components.ialarm.IAlarm") as mock_ialarm_api:
        yield mock_ialarm_api


@pytest.fixture(name="mock_config_entry")
def mock_config_fixture():
    """Return a fake config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.10.20", CONF_PORT: 18034},
        entry_id=str(uuid4()),
    )


async def test_setup_entry(hass, ialarm_api, mock_config_entry):
    """Test setup entry."""
    ialarm_api.return_value.get_mac = Mock(return_value="00:00:54:12:34:56")

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ialarm_api.return_value.get_mac.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_not_ready(hass, ialarm_api, mock_config_entry):
    """Test setup failed because we can't connect to the alarm system."""
    ialarm_api.return_value.get_mac = Mock(side_effect=ConnectionError)

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass, ialarm_api, mock_config_entry):
    """Test being able to unload an entry."""
    ialarm_api.return_value.get_mac = Mock(return_value="00:00:54:12:34:56")

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
