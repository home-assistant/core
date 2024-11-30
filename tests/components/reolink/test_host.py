"""Test the Reolink host."""

from asyncio import CancelledError
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
import pytest
from reolink_aio.enums import SubType
from reolink_aio.exceptions import NotSupportedError, ReolinkError, SubscriptionError

from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL
from homeassistant.components.reolink.host import (
    FIRST_ONVIF_LONG_POLL_TIMEOUT,
    FIRST_ONVIF_TIMEOUT,
    FIRST_TCP_PUSH_TIMEOUT,
    LONG_POLL_COOLDOWN,
    LONG_POLL_ERROR_COOLDOWN,
    POLL_INTERVAL_NO_PUSH,
)
from homeassistant.components.webhook import async_handle_webhook
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.util.aiohttp import MockRequest

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_setup_with_tcp_push(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test successful setup of the integration with TCP push callbacks."""
    reolink_connect.baichuan.events_active = True
    reolink_connect.baichuan.subscribe_events.reset_mock(side_effect=True)
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=FIRST_TCP_PUSH_TIMEOUT))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # ONVIF push subscription not called
    assert not reolink_connect.subscribe.called

    reolink_connect.baichuan.events_active = False
    reolink_connect.baichuan.subscribe_events.side_effect = ReolinkError("Test error")


async def test_unloading_with_tcp_push(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test successful unloading of the integration with TCP push callbacks."""
    reolink_connect.baichuan.events_active = True
    reolink_connect.baichuan.subscribe_events.reset_mock(side_effect=True)
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    reolink_connect.baichuan.unsubscribe_events.side_effect = ReolinkError("Test error")

    # Unload the config entry
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    reolink_connect.baichuan.events_active = False
    reolink_connect.baichuan.subscribe_events.side_effect = ReolinkError("Test error")
    reolink_connect.baichuan.unsubscribe_events.reset_mock(side_effect=True)


async def test_webhook_callback(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test webhook callback with motion sensor."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    webhook_id = config_entry.runtime_data.host.webhook_id

    signal_all = MagicMock()
    signal_ch = MagicMock()
    async_dispatcher_connect(hass, f"{webhook_id}_all", signal_all)
    async_dispatcher_connect(hass, f"{webhook_id}_0", signal_ch)

    client = await hass_client_no_auth()

    # test webhook callback success all channels
    reolink_connect.ONVIF_event_callback.return_value = None
    await client.post(f"/api/webhook/{webhook_id}")
    signal_all.assert_called_once()

    freezer.tick(timedelta(seconds=FIRST_ONVIF_TIMEOUT))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

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
    reolink_connect.ONVIF_event_callback.side_effect = Exception("Test error")
    await client.post(f"/api/webhook/{webhook_id}", data="test_data")
    signal_ch.assert_not_called()

    # test failure to read date from webhook post
    request = MockRequest(
        method="POST",
        content=bytes("test", "utf-8"),
        mock_source="test",
    )
    request.read = AsyncMock()
    request.read.side_effect = ConnectionResetError("Test error")
    await async_handle_webhook(hass, webhook_id, request)
    signal_all.assert_not_called()

    request.read.side_effect = ClientResponseError("Test error", "Test")
    await async_handle_webhook(hass, webhook_id, request)
    signal_all.assert_not_called()

    request.read.side_effect = CancelledError("Test error")
    with pytest.raises(CancelledError):
        await async_handle_webhook(hass, webhook_id, request)
    signal_all.assert_not_called()

    reolink_connect.ONVIF_event_callback.reset_mock(side_effect=True)


async def test_no_mac(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test setup of host with no mac."""
    original = reolink_connect.mac_address
    reolink_connect.mac_address = None
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    reolink_connect.mac_address = original


async def test_subscribe_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test error when subscribing to ONVIF does not block startup."""
    reolink_connect.subscribe.side_effect = ReolinkError("Test Error")
    reolink_connect.subscribed.return_value = False
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    reolink_connect.subscribe.reset_mock(side_effect=True)


async def test_subscribe_unsuccesfull(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test that a unsuccessful ONVIF subscription does not block startup."""
    reolink_connect.subscribed.return_value = False
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED


async def test_initial_ONVIF_not_supported(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test setup when initial ONVIF is not supported."""

    def test_supported(ch, key):
        """Test supported function."""
        if key == "initial_ONVIF_state":
            return False
        return True

    reolink_connect.supported = test_supported

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED


async def test_ONVIF_not_supported(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test setup is not blocked when ONVIF API returns NotSupportedError."""

    def test_supported(ch, key):
        """Test supported function."""
        if key == "initial_ONVIF_state":
            return False
        return True

    reolink_connect.supported = test_supported
    reolink_connect.subscribed.return_value = False
    reolink_connect.subscribe.side_effect = NotSupportedError("Test error")

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    reolink_connect.subscribe.reset_mock(side_effect=True)
    reolink_connect.subscribed.return_value = True


async def test_renew(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test renew of the ONVIF subscription."""
    reolink_connect.renewtimer.return_value = 1

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    reolink_connect.renew.assert_called()

    reolink_connect.renew.side_effect = SubscriptionError("Test error")

    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    reolink_connect.subscribe.assert_called()

    reolink_connect.subscribe.reset_mock()
    reolink_connect.subscribe.side_effect = SubscriptionError("Test error")

    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    reolink_connect.subscribe.assert_called()

    reolink_connect.renew.reset_mock(side_effect=True)
    reolink_connect.subscribe.reset_mock(side_effect=True)


async def test_long_poll_renew_fail(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test ONVIF long polling errors while renewing."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    reolink_connect.subscribe.side_effect = NotSupportedError("Test error")

    freezer.tick(timedelta(seconds=FIRST_ONVIF_TIMEOUT))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # ensure long polling continues
    reolink_connect.pull_point_request.assert_called()

    reolink_connect.subscribe.reset_mock(side_effect=True)


async def test_register_webhook_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test errors while registering the webhook."""
    with patch(
        "homeassistant.components.reolink.host.get_url",
        side_effect=NoURLAvailableError("Test error"),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_long_poll_stop_when_push(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test ONVIF long polling stops when ONVIF push comes in."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    # start ONVIF long polling because ONVIF push did not came in
    freezer.tick(timedelta(seconds=FIRST_ONVIF_TIMEOUT))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # simulate ONVIF push callback
    client = await hass_client_no_auth()
    reolink_connect.ONVIF_event_callback.return_value = None
    webhook_id = config_entry.runtime_data.host.webhook_id
    await client.post(f"/api/webhook/{webhook_id}")

    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    reolink_connect.unsubscribe.assert_called_with(sub_type=SubType.long_poll)


async def test_long_poll_errors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test errors during ONVIF long polling."""
    reolink_connect.pull_point_request.reset_mock()

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    reolink_connect.pull_point_request.side_effect = ReolinkError("Test error")

    # start ONVIF long polling because ONVIF push did not came in
    freezer.tick(timedelta(seconds=FIRST_ONVIF_TIMEOUT))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    reolink_connect.pull_point_request.assert_called_once()
    reolink_connect.pull_point_request.side_effect = Exception("Test error")

    freezer.tick(timedelta(seconds=LONG_POLL_ERROR_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=LONG_POLL_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    reolink_connect.unsubscribe.assert_called_with(sub_type=SubType.long_poll)

    reolink_connect.pull_point_request.reset_mock(side_effect=True)


async def test_fast_polling_errors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test errors during ONVIF fast polling."""
    reolink_connect.get_motion_state_all_ch.reset_mock()
    reolink_connect.get_motion_state_all_ch.side_effect = ReolinkError("Test error")
    reolink_connect.pull_point_request.side_effect = ReolinkError("Test error")

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    # start ONVIF long polling because ONVIF push did not came in
    freezer.tick(timedelta(seconds=FIRST_ONVIF_TIMEOUT))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # start ONVIF fast polling because ONVIF long polling did not came in
    freezer.tick(timedelta(seconds=FIRST_ONVIF_LONG_POLL_TIMEOUT))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert reolink_connect.get_motion_state_all_ch.call_count == 1

    freezer.tick(timedelta(seconds=POLL_INTERVAL_NO_PUSH))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # fast polling continues despite errors
    assert reolink_connect.get_motion_state_all_ch.call_count == 2

    reolink_connect.get_motion_state_all_ch.reset_mock(side_effect=True)
    reolink_connect.pull_point_request.reset_mock(side_effect=True)


async def test_diagnostics_event_connection(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test Reolink diagnostics event connection return values."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag["event connection"] == "Fast polling"

    # start ONVIF long polling because ONVIF push did not came in
    freezer.tick(timedelta(seconds=FIRST_ONVIF_TIMEOUT))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag["event connection"] == "ONVIF long polling"

    # simulate ONVIF push callback
    client = await hass_client_no_auth()
    reolink_connect.ONVIF_event_callback.return_value = None
    webhook_id = config_entry.runtime_data.host.webhook_id
    await client.post(f"/api/webhook/{webhook_id}")

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag["event connection"] == "ONVIF push"

    # set TCP push as active
    reolink_connect.baichuan.events_active = True
    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag["event connection"] == "TCP push"
