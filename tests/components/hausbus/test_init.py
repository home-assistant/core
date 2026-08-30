"""Test the Haus-Bus integration setup and unload."""

from unittest.mock import MagicMock, patch

from homeassistant.components.hausbus.const import DOMAIN, NEW_CHANNEL_ADDED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from tests.common import MockConfigEntry


def _make_channel(object_id: int) -> MagicMock:
    """Return a fake ABusFeature-like channel with a fixed object id."""
    channel = MagicMock()
    channel.getObjectId.return_value = object_id
    return channel


async def test_unload_stops_discovery_before_platform_unload(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """The device listener is removed before the cover platform unloads.

    pyhausbus's DeviceWorker thread can still be processing in-flight
    search replies after discovery has otherwise finished, and the cover
    platform's NEW_CHANNEL_ADDED dispatcher listener is not disconnected
    until async_unload_entry() has returned successfully. A
    newDeviceDetected() callback landing while async_unload_platforms() is
    still running could therefore reach async_add_entities() on a platform
    that is mid-teardown and leave an entity behind. Removing the device
    listener first closes that window - this proves the ordering that
    guarantees it, since the underlying pyhausbus thread race itself is
    outside what a test can control.
    """
    config_entry = MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    call_order: list[str] = []
    mock_home_server.removeBusDeviceListener.side_effect = lambda *args, **kwargs: (
        call_order.append("removeBusDeviceListener")
    )
    original_unload_platforms = hass.config_entries.async_unload_platforms

    async def _tracking_unload_platforms(*args: object, **kwargs: object) -> bool:
        call_order.append("async_unload_platforms")
        return await original_unload_platforms(*args, **kwargs)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        side_effect=_tracking_unload_platforms,
    ):
        assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert call_order == ["removeBusDeviceListener", "async_unload_platforms"]


async def test_unload_restores_device_listener_if_platform_unload_fails(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """The device listener is re-added if the platform fails to unload.

    Otherwise a failed platform unload would silently and permanently stop
    new device discovery for a gateway that keeps running afterwards.
    """
    config_entry = MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    gateway = config_entry.runtime_data

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(config_entry.entry_id)

    mock_home_server.removeBusDeviceListener.assert_called_once_with(gateway)
    # Once at gateway creation, once to restore it after the failed unload.
    assert mock_home_server.addBusDeviceListener.call_args_list == [
        ((gateway,),),
        ((gateway,),),
    ]
    mock_home_server.shutdown.assert_not_called()


async def test_unload_buffers_channel_discovered_during_platform_unload(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Test that channels discovered during platform unload are buffered."""
    config_entry = MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    gateway = config_entry.runtime_data

    received: list[tuple] = []
    async_dispatcher_connect(
        hass, NEW_CHANNEL_ADDED, lambda *args: received.append(args)
    )

    channel = _make_channel(99)
    device_info = DeviceInfo(identifiers={(DOMAIN, "99")})
    original_unload_platforms = hass.config_entries.async_unload_platforms

    async def _late_discovery_unload_platforms(*args: object, **kwargs: object) -> bool:
        gateway._register_channel(channel, device_info)
        return await original_unload_platforms(*args, **kwargs)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        side_effect=_late_discovery_unload_platforms,
    ):
        assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert received == []
    assert gateway._pending_channels == [(channel, device_info)]


async def test_unload_flushes_buffered_channel_if_platform_unload_fails(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """A channel buffered during unload is dispatched once the unload fails.

    Mirrors test_unload_restores_device_listener_if_platform_unload_fails,
    but for gateway.pause_channel_dispatch()/async_flush_pending_channels()
    instead of the pyhausbus listener: a failed unload must not leave a
    channel discovered during the attempt stuck in the buffer forever.
    """
    config_entry = MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    gateway = config_entry.runtime_data

    received: list[tuple] = []
    async_dispatcher_connect(
        hass, NEW_CHANNEL_ADDED, lambda *args: received.append(args)
    )

    channel = _make_channel(100)
    device_info = DeviceInfo(identifiers={(DOMAIN, "100")})

    async def _late_discovery_unload_platforms(*args: object, **kwargs: object) -> bool:
        gateway._register_channel(channel, device_info)
        return False

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        side_effect=_late_discovery_unload_platforms,
    ):
        assert not await hass.config_entries.async_unload(config_entry.entry_id)

    assert received == [(channel, device_info)]
    assert gateway._pending_channels == []
