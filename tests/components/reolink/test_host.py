"""Test the Reolink host."""

from asyncio import CancelledError
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.reolink import const
from homeassistant.components.webhook import async_handle_webhook
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.aiohttp import MockRequest

from .conftest import TEST_UID

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_webhook_callback(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test webhook callback with motion sensor."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    webhook_id = f"{const.DOMAIN}_{TEST_UID.replace(':', '')}_ONVIF"

    signal_all = MagicMock()
    signal_ch = MagicMock()
    async_dispatcher_connect(hass, f"{webhook_id}_all", signal_all)
    async_dispatcher_connect(hass, f"{webhook_id}_0", signal_ch)

    client = await hass_client_no_auth()

    # test webhook callback success all channels
    reolink_connect.ONVIF_event_callback.return_value = None
    await client.post(f"/api/webhook/{webhook_id}")
    signal_all.assert_called_once()

    # test webhook callback all channels with failure to read motion_state
    signal_all.reset_mock()
    reolink_connect.get_motion_state_all_ch.return_value = False
    await client.post(f"/api/webhook/{webhook_id}")
    signal_all.assert_not_called()

    # test webhook callback success single channel
    reolink_connect.ONVIF_event_callback.return_value = [0]
    await client.post(f"/api/webhook/{webhook_id}", data="test_data")
    signal_ch.assert_called_once()

    # test webhook callback single channel with error in event callback
    signal_ch.reset_mock()
    reolink_connect.ONVIF_event_callback = AsyncMock(
        side_effect=Exception("Test error")
    )
    await client.post(f"/api/webhook/{webhook_id}", data="test_data")
    signal_ch.assert_not_called()

    # test failure to read date from webhook post
    request = MockRequest(
        method="POST",
        content=bytes("test", "utf-8"),
        mock_source="test",
    )
    request.read = AsyncMock(side_effect=ConnectionResetError("Test error"))
    await async_handle_webhook(hass, webhook_id, request)
    signal_all.assert_not_called()

    request.read = AsyncMock(side_effect=ClientResponseError("Test error", "Test"))
    await async_handle_webhook(hass, webhook_id, request)
    signal_all.assert_not_called()

    request.read = AsyncMock(side_effect=CancelledError("Test error"))
    with pytest.raises(CancelledError):
        await async_handle_webhook(hass, webhook_id, request)
    signal_all.assert_not_called()
