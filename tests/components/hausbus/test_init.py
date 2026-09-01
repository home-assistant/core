"""Test the Haus-Bus integration setup and unload."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.hausbus.const import DOMAIN, NEW_CHANNEL_ADDED
from homeassistant.components.hausbus.gateway import async_acquire_home_server
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from tests.common import MockConfigEntry


def _make_channel(object_id: int) -> MagicMock:
    """Return a fake ABusFeature-like channel with a fixed object id."""
    channel = MagicMock()
    channel.getObjectId.return_value = object_id
    return channel


def _make_module_id() -> MagicMock:
    """Return a fake ModuleId as passed to newDeviceDetected()."""
    module_id = MagicMock()
    module_id.getFirmwareId.return_value.getTemplateId.return_value = "template"
    module_id.getMajorRelease.return_value = 1
    module_id.getMinorRelease.return_value = 0
    module_id.getName.return_value = "Controller"
    return module_id


async def test_unload_stops_discovery_before_platform_unload(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """The device listener is removed before the cover platform unloads.

    Proves the ordering async_unload_entry() relies on to avoid
    dispatching into a mid-teardown platform (see its comment) - the
    underlying pyhausbus thread race itself is outside what a test can
    control.
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
    """A channel discovered while async_unload_platforms() runs is buffered, not dispatched.

    Goes through the real newDeviceDetected() callback rather than the
    private _register_channel(), so it survives internal refactors.
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

    channel = _make_channel(99)
    original_unload_platforms = hass.config_entries.async_unload_platforms

    async def _late_discovery_unload_platforms(*args: object, **kwargs: object) -> bool:
        gateway.newDeviceDetected(
            99, "Rolladen", _make_module_id(), MagicMock(), [channel]
        )
        await hass.async_block_till_done()
        return await original_unload_platforms(*args, **kwargs)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        side_effect=_late_discovery_unload_platforms,
    ):
        assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert received == []


async def test_unload_flushes_buffered_channel_if_platform_unload_fails(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """A channel buffered during unload is dispatched once the unload fails.

    Goes through the real newDeviceDetected() callback rather than the
    private _register_channel(), so it survives internal refactors.
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

    async def _late_discovery_unload_platforms(*args: object, **kwargs: object) -> bool:
        gateway.newDeviceDetected(
            100, "Rolladen", _make_module_id(), MagicMock(), [channel]
        )
        await hass.async_block_till_done()
        return False

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        side_effect=_late_discovery_unload_platforms,
    ):
        assert not await hass.config_entries.async_unload(config_entry.entry_id)

    assert [chan for chan, _device_info in received] == [channel]


@pytest.mark.parametrize("error", [OSError, TimeoutError])
async def test_setup_retries_if_home_server_connection_fails(
    hass: HomeAssistant,
    mock_home_server_class: MagicMock,
    error: type[Exception],
) -> None:
    """Setup enters the retry path if opening the connection fails.

    HausbusGateway.async_create() constructs HomeServer() on the executor;
    async_setup_entry() must turn that failure into a retry rather than
    failing setup outright or letting the exception escape unconverted.
    """
    config_entry = MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})
    config_entry.add_to_hass(hass)
    mock_home_server_class.side_effect = error("connection failed")

    assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_releases_home_server_if_platform_setup_fails(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Bus listeners and the HomeServer are released if platform setup fails.

    async_setup_entry() re-raises after cleaning up, but the config entry
    framework catches that internally and returns False rather than
    propagating it - so the cleanup itself is what a retry depends on.
    """
    config_entry = MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})
    config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("platform setup boom"),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    gateway = config_entry.runtime_data
    mock_home_server.removeBusEventListener.assert_called_once_with(gateway)
    mock_home_server.removeBusDeviceListener.assert_called_once_with(gateway)
    mock_home_server.shutdown.assert_called_once()


async def test_unload_shutdown_failure_is_not_handed_out_again(
    hass: HomeAssistant,
    mock_home_server: MagicMock,
    mock_home_server_class: MagicMock,
) -> None:
    """A failed shutdown completes unload and blocks later acquisitions."""
    config_entry = MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_home_server.shutdown.side_effect = RuntimeError("DeviceWorker failed to stop")

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    # A fresh HomeServer() call returns a distinct object, as pyhausbus's
    # real singleton does after shutdown() clears it.
    mock_home_server_class.return_value = MagicMock()

    with pytest.raises(OSError):
        await async_acquire_home_server(hass)
