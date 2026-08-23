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
from homeassistant.helpers import device_registry as dr
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


async def test_new_device_detected_registers_device_and_dispatches_channel(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """A newly discovered device is registered and its channel dispatched."""
    gateway = _make_gateway(hass, mock_home_server)

    received: list[tuple[MagicMock, DeviceInfo]] = []
    async_dispatcher_connect(
        hass,
        NEW_CHANNEL_ADDED,
        lambda channel, device_info: received.append((channel, device_info)),
    )

    channel = _make_channel(device_id=100, instance_id=1)

    await hass.async_add_executor_job(
        gateway.newDeviceDetected,
        100,
        "ESP32 Controller",
        _make_module_id(),
        MagicMock(),
        [channel],
    )
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "100")})
    assert device is not None
    assert device.manufacturer == "HausBus"
    assert device.model == "ESP32 Controller"

    assert len(received) == 1
    assert received[0][0] is channel


async def test_new_device_detected_dedups_known_channels(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """The same channel is only ever dispatched once, even if seen again."""
    gateway = _make_gateway(hass, mock_home_server)

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


async def test_register_device_is_idempotent(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Registering the same device twice does not create a duplicate entry."""
    gateway = _make_gateway(hass, mock_home_server)

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "100")},
        manufacturer="HausBus",
        model="ESP32 Controller",
        name="ESP32 Controller 100",
    )

    await gateway.async_register_device(100, device_info)
    await gateway.async_register_device(100, device_info)

    device_registry = dr.async_get(hass)
    devices = [
        device
        for device in device_registry.devices.values()
        if (DOMAIN, "100") in device.identifiers
    ]
    assert len(devices) == 1
