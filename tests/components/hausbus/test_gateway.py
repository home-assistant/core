"""Tests for the Haus-Bus gateway."""

from unittest.mock import MagicMock

from pyhausbus import HausBusUtils
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Rollladen import Rollladen

from homeassistant.components.hausbus.const import DOMAIN, NEW_CHANNEL_ADDED
from homeassistant.components.hausbus.gateway import HausbusGateway
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from tests.common import MockConfigEntry


def _make_channel(device_id: int, instance_id: int) -> MagicMock:
    """Create a mock Rollladen channel with a real, decodable object id."""
    channel = MagicMock(spec=Rollladen)
    channel.getObjectId.return_value = HausBusUtils.getObjectId(
        device_id, Rollladen.CLASS_ID, instance_id
    )
    channel.getName.return_value = f"Rollladen {instance_id}"
    return channel


def _make_module_id() -> MagicMock:
    """Create a mock ModuleId with the fields newDeviceDetected reads."""
    module_id = MagicMock(spec=ModuleId)
    module_id.getFirmwareId.return_value = EFirmwareId.ESP32
    module_id.getMajorRelease.return_value = 1
    module_id.getMinorRelease.return_value = 0
    module_id.getName.return_value = "ESP32"
    return module_id


def _make_gateway(hass: HomeAssistant, home_server: MagicMock) -> HausbusGateway:
    """Create a gateway directly, without going through config entry setup."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    return HausbusGateway(hass, entry, home_server)


async def test_new_device_detected_dispatches_channel(
    hass: HomeAssistant,
    mock_home_server: MagicMock,
) -> None:
    """A newly discovered device dispatches its channel with the correct DeviceInfo."""
    gateway = _make_gateway(hass, mock_home_server)

    received: list[tuple[MagicMock, DeviceInfo]] = []
    async_dispatcher_connect(
        hass,
        NEW_CHANNEL_ADDED,
        lambda channel, device_info: received.append((channel, device_info)),
    )

    channel = _make_channel(device_id=100, instance_id=1)

    # Simulate platform setup completing before discovery.
    await gateway.async_flush_pending_channels()

    await hass.async_add_executor_job(
        gateway.newDeviceDetected,
        100,
        "ESP32 Controller",
        _make_module_id(),
        MagicMock(),
        [channel],
    )
    await hass.async_block_till_done()

    assert len(received) == 1
    assert received[0][0] is channel
    device_info = received[0][1]
    assert device_info["manufacturer"] == "HausBus"
    assert device_info["model"] == "ESP32 Controller"


async def test_new_device_detected_before_platform_ready_is_flushed_after(
    hass: HomeAssistant,
    mock_home_server: MagicMock,
) -> None:
    """Channels discovered before platform setup is complete are delivered after flush."""
    gateway = _make_gateway(hass, mock_home_server)

    received: list[tuple[MagicMock, DeviceInfo]] = []
    async_dispatcher_connect(
        hass,
        NEW_CHANNEL_ADDED,
        lambda channel, device_info: received.append((channel, device_info)),
    )

    channel = _make_channel(device_id=100, instance_id=1)

    # Simulate discovery firing before async_forward_entry_setups completes.
    await hass.async_add_executor_job(
        gateway.newDeviceDetected,
        100,
        "ESP32 Controller",
        _make_module_id(),
        MagicMock(),
        [channel],
    )
    await hass.async_block_till_done()

    # Channel was buffered, not dispatched yet.
    assert len(received) == 0

    # Platform setup completes; buffered channels are flushed.
    await gateway.async_flush_pending_channels()
    await hass.async_block_till_done()

    assert len(received) == 1
    assert received[0][0] is channel


async def test_new_device_detected_dedups_known_channels(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """The same channel is only ever dispatched once, even if seen again."""
    gateway = _make_gateway(hass, mock_home_server)
    await gateway.async_flush_pending_channels()

    dispatch_mock = MagicMock()
    async_dispatcher_connect(hass, NEW_CHANNEL_ADDED, dispatch_mock)

    channel = _make_channel(device_id=100, instance_id=1)
    module_id = _make_module_id()

    for _ in range(2):
        await hass.async_add_executor_job(
            gateway.newDeviceDetected,
            100,
            "ESP32 Controller",
            module_id,
            MagicMock(),
            [channel],
        )
    await hass.async_block_till_done()

    dispatch_mock.assert_called_once()


async def test_bus_data_received_ignores_internal_device(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Messages that originate from the Haus-Bus server itself are ignored."""
    gateway = _make_gateway(hass, mock_home_server)
    mock_home_server.is_internal_device.return_value = True

    object_id = HausBusUtils.getObjectId(100, Rollladen.CLASS_ID, 1)
    received = MagicMock()
    async_dispatcher_connect(hass, f"hausbus_update_{object_id}", received)

    gateway.busDataReceived(BusDataMessage(object_id, 0, MagicMock()))
    await hass.async_block_till_done()

    received.assert_not_called()


async def test_bus_data_received_dispatches_update(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Messages from other devices are dispatched to the matching entity."""
    gateway = _make_gateway(hass, mock_home_server)
    mock_home_server.is_internal_device.return_value = False

    object_id = HausBusUtils.getObjectId(100, Rollladen.CLASS_ID, 1)
    received = MagicMock()
    async_dispatcher_connect(hass, f"hausbus_update_{object_id}", received)

    data = MagicMock()
    gateway.busDataReceived(BusDataMessage(object_id, 0, data))
    await hass.async_block_till_done()

    received.assert_called_once_with(data)
