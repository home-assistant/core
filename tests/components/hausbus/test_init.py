"""Test the Haus-Bus integration setup and unload."""

from unittest.mock import MagicMock, patch

from homeassistant.components.hausbus.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
