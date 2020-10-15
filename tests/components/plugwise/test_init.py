"""Tests for the Plugwise Climate integration."""

import asyncio

from Plugwise_Smile.Smile import Smile

from homeassistant.components import plugwise
from homeassistant.components.plugwise import DOMAIN
from homeassistant.components.plugwise.gateway import SERVICE_DELETE
from homeassistant.config_entries import (
    ENTRY_STATE_SETUP_ERROR,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.setup import async_setup_component

from tests.common import AsyncMock, MockConfigEntry
from tests.components.plugwise.common import async_init_integration


async def test_smile_unauthorized(hass, mock_smile_unauth):
    """Test failing unauthorization by Smile."""
    entry = await async_init_integration(hass, mock_smile_unauth)
    assert entry.state == ENTRY_STATE_SETUP_ERROR


async def test_smile_error(hass, mock_smile_error):
    """Test server error handling by Smile."""
    entry = await async_init_integration(hass, mock_smile_error)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_smile_notconnect(hass, mock_smile_notconnect):
    """Connection failure error handling by Smile."""
    mock_smile_notconnect.connect.return_value = False
    entry = await async_init_integration(hass, mock_smile_notconnect)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_smile_timeout(hass, mock_smile_notconnect):
    """Timeout error handling by Smile."""
    mock_smile_notconnect.connect.side_effect = asyncio.TimeoutError
    entry = await async_init_integration(hass, mock_smile_notconnect)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_smile_adam_xmlerror(hass, mock_smile_adam):
    """Detect malformed XML by Smile in Adam environment."""
    mock_smile_adam.full_update_device.side_effect = Smile.XMLDataMissingError
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass, mock_smile_adam):
    """Test being able to unload an entry."""
    entry = await async_init_integration(hass, mock_smile_adam)

    mock_smile_adam.async_reset = AsyncMock(return_value=True)
    assert await plugwise.async_unload_entry(hass, entry)
    assert not hass.data[DOMAIN]


async def test_unload_gateway_entry(hass, mock_smile_adam):
    """Test being able to unload an entry."""
    entry = await async_init_integration(hass, mock_smile_adam)

    mock_smile_adam.async_reset = AsyncMock(return_value=True)
    assert await plugwise.gateway.async_unload_entry(hass, entry)
    assert not hass.data[DOMAIN]


async def test_async_setup_entry_fail(hass):
    """Test async_setup_entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    config = {}

    await async_setup_component(hass, "plugwise", config)
    await hass.async_block_till_done()
    assert not await plugwise.async_setup_entry(hass, entry)


async def test_async_notification_delete(hass, mock_smile_adam):
    """Test notification delete on climate Smile."""
    await async_init_integration(hass, mock_smile_adam)

    await hass.services.async_call(DOMAIN, SERVICE_DELETE)


async def test_async_notification_delete_failure(hass, mock_smile_anna):
    """Test notification delete on cliamte Smile."""
    await async_init_integration(hass, mock_smile_anna)

    await hass.services.async_call(DOMAIN, SERVICE_DELETE)
