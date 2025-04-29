"""Tests for the Dreo integration."""

from unittest.mock import MagicMock, patch

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException

from homeassistant.components.dreo.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(hass: HomeAssistant) -> None:
    """Test loading and unloading the config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    # Mock the HsCloud instance
    mock_manager = MagicMock(spec=HsCloud)
    mock_manager.login.return_value = None
    mock_manager.get_devices.return_value = []

    with patch(
        "homeassistant.components.dreo.HsCloud",
        return_value=mock_manager,
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    # Test unloading the config entry
    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is not ConfigEntryState.LOADED


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Test the Dreo configuration entry not ready."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    # Mock the HsCloud instance to raise an exception
    mock_manager = MagicMock(spec=HsCloud)
    mock_manager.login.side_effect = HsCloudException("Connection failed")

    with patch(
        "homeassistant.components.dreo.HsCloud",
        return_value=mock_manager,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.SETUP_ERROR


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    # Mock the HsCloud instance to raise an auth exception
    mock_manager = MagicMock(spec=HsCloud)
    mock_manager.login.side_effect = HsCloudBusinessException("Invalid credentials")

    with patch(
        "homeassistant.components.dreo.HsCloud",
        return_value=mock_manager,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.SETUP_RETRY
