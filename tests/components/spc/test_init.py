"""Tests for Vanderbilt SPC component."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from pyspcwebgw.area import Area
from pyspcwebgw.zone import Zone

from homeassistant.components.spc.const import (
    DOMAIN,
    SIGNAL_UPDATE_ALARM,
    SIGNAL_UPDATE_SENSOR,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import TEST_CONFIG

from tests.common import MockConfigEntry


async def test_valid_device_config(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test valid device config."""
    mock_client.return_value.async_load_parameters.return_value = True
    assert await async_setup_component(hass, DOMAIN, {"spc": TEST_CONFIG}) is True


async def test_invalid_device_config(hass: HomeAssistant) -> None:
    """Test invalid device config."""
    config = {"spc": {"api_url": "http://localhost/"}}  # Missing ws_url
    assert await async_setup_component(hass, DOMAIN, config) is False


async def test_setup_entry_not_ready(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test that it sets up retry when exception occurs during setup."""
    client = mock_client.return_value
    client.async_load_parameters.side_effect = ClientError()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)


async def test_setup_entry_failed(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test that it handles setup failure."""
    client = mock_client.return_value
    client.async_load_parameters.return_value = False

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)


async def test_missing_config_items(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test missing required config items."""
    await async_setup_component(hass, DOMAIN, {"spc": {}})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0


async def test_update_callback(
    hass: HomeAssistant, mock_client: AsyncMock, mock_area: Area, mock_zone: Zone
) -> None:
    """Test update callback dispatching."""
    mock_client.return_value.async_load_parameters.return_value = True
    with patch("homeassistant.components.spc.async_dispatcher_send") as mock_dispatch:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=TEST_CONFIG,
            entry_id="test",
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        callback = mock_client.call_args[1]["async_callback"]
        await callback(mock_area)
        mock_dispatch.assert_called_with(hass, SIGNAL_UPDATE_ALARM.format(mock_area.id))

        await callback(mock_zone)
        mock_dispatch.assert_called_with(
            hass, SIGNAL_UPDATE_SENSOR.format(mock_zone.id)
        )


async def test_setup_unload_and_reload_entry(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test entry setup and unload."""
    mock_client.return_value.async_load_parameters.return_value = True
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)


async def _setup_spc_entry(hass: HomeAssistant) -> None:
    """Set up SPC entry for testing."""
    await async_setup_component(hass, DOMAIN, {"spc": TEST_CONFIG})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    if entries:
        await hass.config_entries.async_setup(entries[0].entry_id)
