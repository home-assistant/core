"""Tests for the Bbox integration setup."""

from unittest.mock import MagicMock

from bbox_api import (
    BboxConnectionError,
    BboxInvalidCredentialsError,
    BboxRateLimitError,
)
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.bbox.const import DOMAIN
from homeassistant.components.bbox.coordinator import BboxCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from .const import DEVICE, HOST, HOSTS, STATS


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry sets up the coordinator and forwards the platforms."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator: BboxCoordinator = mock_config_entry.runtime_data
    assert coordinator.data.device is DEVICE
    assert coordinator.data.stats is STATS
    assert coordinator.data.hosts == HOSTS

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_without_password_triggers_reauth(hass: HomeAssistant) -> None:
    """Test an imported entry without password asks for reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        data={CONF_HOST: HOST, CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_cannot_connect(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an unreachable box puts the entry in SETUP_RETRY."""
    mock_bbox_client.return_value.get_device.side_effect = BboxConnectionError("down")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_invalid_credentials(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test wrong credentials put the entry in SETUP_ERROR (reauth)."""
    mock_bbox_client.return_value.get_hosts.side_effect = BboxInvalidCredentialsError()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_rate_limited(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a 429 from the box is a plain retry later, not an auth failure."""
    mock_bbox_client.return_value.get_device.side_effect = BboxRateLimitError()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
