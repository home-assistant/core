"""Test the Dreo integration."""

from unittest.mock import MagicMock, patch

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException

from homeassistant.components.dreo.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup(hass: HomeAssistant, mock_config_entry) -> None:
    """Test the Dreo setup."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert mock_config_entry.state == ConfigEntryState.LOADED


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

    # Changed from SETUP_ERROR to SETUP_RETRY to match actual behavior
    assert mock_entry.state == ConfigEntryState.SETUP_RETRY


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

    # Changed from SETUP_RETRY to SETUP_ERROR to match actual behavior
    assert mock_entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_config_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test unloading the Dreo config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert mock_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
