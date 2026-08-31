"""Test the Haus-Bus gateway."""

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.hausbus.const import NEW_CHANNEL_ADDED
from homeassistant.components.hausbus.gateway import (
    HausbusGateway,
    async_acquire_home_server,
    async_release_home_server,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect


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


@pytest.fixture
def gateway(hass: HomeAssistant, mock_home_server: MagicMock) -> HausbusGateway:
    """Return a gateway wired up to the mocked HomeServer."""
    return HausbusGateway(hass, MagicMock(), mock_home_server)


def test_init_registers_bus_listeners(
    gateway: HausbusGateway, mock_home_server: MagicMock
) -> None:
    """The gateway registers itself as event and device listener on creation."""
    mock_home_server.addBusEventListener.assert_called_once_with(gateway)
    mock_home_server.addBusDeviceListener.assert_called_once_with(gateway)


async def test_async_create_acquires_home_server(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """async_create() acquires a HomeServer reference and wires the gateway to it."""
    config_entry = MagicMock()

    created = await HausbusGateway.async_create(hass, config_entry)

    assert created.home_server is mock_home_server
    mock_home_server.addBusEventListener.assert_called_once_with(created)

    # async_create() must have taken out a reference: releasing it once is
    # enough to shut the shared HomeServer back down.
    await async_release_home_server(hass, created.home_server)
    mock_home_server.shutdown.assert_called_once()


async def test_register_channel_ignores_duplicates(
    hass: HomeAssistant, gateway: HausbusGateway
) -> None:
    """A channel discovered twice is only dispatched once."""
    await gateway.async_flush_pending_channels()
    channel = _make_channel(1)

    received: list[tuple] = []
    async_dispatcher_connect(
        hass, NEW_CHANNEL_ADDED, lambda *args: received.append(args)
    )

    gateway.newDeviceDetected(
        1, "Controller", _make_module_id(), MagicMock(), [channel]
    )
    gateway.newDeviceDetected(
        1, "Controller", _make_module_id(), MagicMock(), [channel]
    )
    await hass.async_block_till_done()

    assert len(received) == 1
    assert gateway.registered_channels == {1}


async def test_register_channel_buffers_until_platform_ready(
    hass: HomeAssistant, gateway: HausbusGateway
) -> None:
    """Channels discovered before platform setup are buffered, not dispatched."""
    channel = _make_channel(2)

    received: list[tuple] = []
    async_dispatcher_connect(
        hass, NEW_CHANNEL_ADDED, lambda *args: received.append(args)
    )

    gateway.newDeviceDetected(
        2, "Controller", _make_module_id(), MagicMock(), [channel]
    )
    await hass.async_block_till_done()

    # Buffered: not dispatched yet, but still recognized as already
    # discovered (a duplicate report of it must not be queued twice).
    assert received == []
    gateway.newDeviceDetected(
        2, "Controller", _make_module_id(), MagicMock(), [channel]
    )
    await hass.async_block_till_done()
    assert received == []

    await gateway.async_flush_pending_channels()
    await hass.async_block_till_done()

    assert len(received) == 1
    assert gateway.registered_channels == {2}

    # Channels discovered after the flush are dispatched immediately.
    other_channel = _make_channel(3)
    gateway.newDeviceDetected(
        3, "Controller", _make_module_id(), MagicMock(), [other_channel]
    )
    await hass.async_block_till_done()
    assert len(received) == 2


async def test_new_device_detected_registers_each_channel(
    hass: HomeAssistant, gateway: HausbusGateway
) -> None:
    """newDeviceDetected() hands each channel to _register_channel via the event loop."""
    await gateway.async_flush_pending_channels()
    first_channel = _make_channel(4)
    second_channel = _make_channel(5)

    received: list[tuple] = []
    async_dispatcher_connect(
        hass, NEW_CHANNEL_ADDED, lambda *args: received.append(args)
    )

    gateway.newDeviceDetected(
        6, "Controller", _make_module_id(), MagicMock(), [first_channel, second_channel]
    )
    await hass.async_block_till_done()

    assert len(received) == 2
    assert gateway.registered_channels == {4, 5}


async def test_bus_data_received_ignores_internal_device(
    hass: HomeAssistant, gateway: HausbusGateway, mock_home_server: MagicMock
) -> None:
    """Messages from the gateway's own internal device are not dispatched."""
    mock_home_server.is_internal_device.return_value = True

    message = MagicMock()
    message.getSenderObjectId.return_value = 0

    received: list[tuple] = []
    async_dispatcher_connect(
        hass, "hausbus_update_0", lambda *args: received.append(args)
    )

    gateway.busDataReceived(message)
    await hass.async_block_till_done()

    assert received == []


async def test_bus_data_received_dispatches_update(
    hass: HomeAssistant, gateway: HausbusGateway, mock_home_server: MagicMock
) -> None:
    """Messages from a real device are dispatched under hausbus_update_<object_id>."""
    mock_home_server.is_internal_device.return_value = False

    message = MagicMock()
    message.getSenderObjectId.return_value = 42
    message.getData.return_value = "payload"

    received: list[tuple] = []
    async_dispatcher_connect(
        hass, "hausbus_update_42", lambda *args: received.append(args)
    )

    gateway.busDataReceived(message)
    await hass.async_block_till_done()

    assert received == [("payload",)]


async def test_start_discovery_calls_search_devices(
    hass: HomeAssistant, gateway: HausbusGateway, mock_home_server: MagicMock
) -> None:
    """start_discovery() triggers a Haus-Bus device search."""
    await gateway.start_discovery()
    mock_home_server.searchDevices.assert_called_once()


async def test_acquire_release_home_server_is_reference_counted(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """The shared HomeServer is only shut down once every acquirer has released it."""
    first = await async_acquire_home_server(hass)
    second = await async_acquire_home_server(hass)
    assert first is second is mock_home_server

    await async_release_home_server(hass, first)
    mock_home_server.shutdown.assert_not_called()

    await async_release_home_server(hass, second)
    mock_home_server.shutdown.assert_called_once()


async def test_release_home_server_surfaces_shutdown_runtime_error(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """A HomeServer that fails to fully stop must be reported, not hidden.

    pyhausbus's shutdown() raises RuntimeError if its background worker or
    collector thread is still alive after its own join timeout. Silently
    treating that as a successful release would let a stray thread from
    the old HomeServer keep running against state a subsequent reload
    replaces, so async_release_home_server() must let it propagate.
    """
    mock_home_server.shutdown.side_effect = RuntimeError("DeviceWorker failed to stop")

    home_server = await async_acquire_home_server(hass)

    with pytest.raises(RuntimeError, match="DeviceWorker failed to stop"):
        await async_release_home_server(hass, home_server)

    mock_home_server.shutdown.assert_called_once()


async def test_cancelled_acquire_shuts_down_home_server_once_constructed(
    hass: HomeAssistant,
) -> None:
    """A HomeServer must be shut down even if constructed after cancellation.

    Regression test: a HomeServer that finishes constructing after its
    acquirer was cancelled must still be shut down, instead of leaking its
    socket and worker threads, as long as nothing else has since acquired it.
    """
    construction_started = threading.Event()
    release_construction = threading.Event()
    home_server = MagicMock()

    def _slow_construct() -> MagicMock:
        construction_started.set()
        assert release_construction.wait(timeout=5), "test did not release in time"
        return home_server

    # `new=` rather than `side_effect=`: hass's test-mode
    # async_add_executor_job() special-cases a Mock target and runs it
    # inline, so it could never be observed in flight.
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        new=_slow_construct,
    ):
        acquire_task = hass.async_create_task(async_acquire_home_server(hass))

        # Wait until the executor-backed constructor call has actually
        # started, so cancelling below lands while it is still running -
        # not before hass.async_add_executor_job() has even scheduled it.
        await hass.async_add_executor_job(construction_started.wait, 5)

        # async_acquire_home_server()'s except-CancelledError branch itself
        # awaits home_server_job (to know whether it needs cleaning up)
        # before re-raising, so it will not actually finish until the
        # executor job does - release it right after cancelling, not after
        # awaiting the task below.
        acquire_task.cancel()
        release_construction.set()

        with pytest.raises(asyncio.CancelledError):
            await acquire_task

        await hass.async_block_till_done(wait_background_tasks=True)

    # Nothing else ever acquired a reference to it, so the HomeServer that
    # finished constructing after cancellation must not be left running.
    home_server.shutdown.assert_called_once()
