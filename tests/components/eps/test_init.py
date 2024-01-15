"""Test the EPS init."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.eps.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="eps_api")
def eps_api_fixture():
    """Set up EPS API fixture."""
    with patch("homeassistant.components.eps.EPS") as mock_eps_api:
        yield mock_eps_api


@pytest.fixture(name="mock_config_entry")
def mock_config_fixture():
    """Return a fake config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "Bob",
            CONF_PASSWORD: "my password",
            CONF_TOKEN: "DSJDKSHDJKZHE",
        },
        entry_id=str(123),
    )


async def test_setup_entry(hass: HomeAssistant, eps_api, mock_config_entry) -> None:
    """Test setup entry."""
    eps_api.return_value.get_site = Mock(return_value="123")

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    eps_api.return_value.get_site.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_not_ready(hass: HomeAssistant, eps_api, mock_config_entry) -> None:
    """Test setup failed because we can't connect to the alarm system."""
    eps_api.return_value.get_site = Mock(side_effect=ConnectionError)

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, eps_api, mock_config_entry) -> None:
    """Test being able to unload an entry."""
    eps_api.return_value.get_site = Mock(return_value="123")

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
