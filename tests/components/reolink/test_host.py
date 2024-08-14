"""Test the Reolink host."""

from asyncio import CancelledError
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL, const
from homeassistant.components.webhook import async_handle_webhook
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.aiohttp import MockRequest
from homeassistant.util.dt import utcnow

from .conftest import TEST_NVR_NAME, TEST_UID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator


async def test_webhook_callback(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test webhook callback with motion sensor."""
    assert await hass.config_entries.async_setup(config_entry.entry_id) is True
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
    reolink_connect.get_motion_state_all_ch.return_value = False
    await client.post(f"/api/webhook/{webhook_id}")
    signal_all.assert_called_once()

    # test webhook callback success single channel
    reolink_connect.ONVIF_event_callback.return_value = [0]
    await client.post(f"/api/webhook/{webhook_id}", data="test_data")
    signal_ch.assert_called_once()

    # test webhook callback single channel with error in event callback
    reolink_connect.ONVIF_event_callback = AsyncMock(
        side_effect=Exception("Test error")
    )
    await client.post(f"/api/webhook/{webhook_id}", data="test_data")
    signal_ch.assert_called_once()

    # test failure to read date from webhook post
    request = MockRequest(
        method="POST",
        content=bytes("test", "utf-8"),
        mock_source="test",
    )
    request.read = AsyncMock(side_effect=ConnectionResetError("Test error"))
    await async_handle_webhook(hass, webhook_id, request)
    signal_all.assert_called_once()

    request.read = AsyncMock(side_effect=ClientResponseError("Test error", "Test"))
    await async_handle_webhook(hass, webhook_id, request)
    signal_all.assert_called_once()

    request.read = AsyncMock(side_effect=CancelledError("Test error"))
    with pytest.raises(CancelledError):
        await async_handle_webhook(hass, webhook_id, request)
    signal_all.assert_called_once()
