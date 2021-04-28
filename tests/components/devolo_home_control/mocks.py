"""Mocks for tests."""

from unittest.mock import MagicMock

from devolo_home_control_api.publisher.publisher import Publisher
from devolo_home_control_api.publisher.updater import Updater


class BinarySensorPropertyMock:
    """devolo Home Control binary sensor mock."""

    element_uid = "Test"
    key_count = 1
    sensor_type = "door"
    sub_type = ""
    state = False


class SettingsMock:
    """devolo Home Control settings mock."""

    name = "Test"
    zone = "Test"


class DeviceMock:
    """devolo Home Control device mock."""

    available = True
    brand = "devolo"
    name = "Test Device"
    uid = "Test"
    settings_property = {"general_device_settings": SettingsMock()}

    def is_online(self):
        """Mock online state of the device."""
        return DeviceMock.available


class BinarySensorMock(DeviceMock):
    """devolo Home Control binary sensor device mock."""

    binary_sensor_property = {"Test": BinarySensorPropertyMock()}


class RemoteControlMock(DeviceMock):
    """devolo Home Control remote control device mock."""

    remote_control_property = {"Test": BinarySensorPropertyMock()}


class DisabledBinarySensorMock(DeviceMock):
    """devolo Home Control disabled binary sensor device mock."""

    binary_sensor_property = {"devolo.WarningBinaryFI:Test": BinarySensorPropertyMock()}


class HomeControlMock:
    """devolo Home Control gateway mock."""

    binary_sensor_devices = []
    binary_switch_devices = []
    multi_level_sensor_devices = []
    multi_level_switch_devices = []
    devices = {}
    publisher = MagicMock()

    def websocket_disconnect(self):
        """Mock disconnect of the websocket."""
        pass


class HomeControlMockBinarySensor(HomeControlMock):
    """devolo Home Control gateway mock with binary sensor device."""

    binary_sensor_devices = [BinarySensorMock()]
    devices = {"Test": BinarySensorMock()}
    publisher = Publisher(devices.keys())
    updater = Updater(devices=devices, gateway=None, publisher=publisher)


class HomeControlMockRemoteControl(HomeControlMock):
    """devolo Home Control gateway mock with remote control device."""

    devices = {"Test": RemoteControlMock()}
    publisher = Publisher(devices.keys())


class HomeControlMockDisabledBinarySensor(HomeControlMock):
    """devolo Home Control gateway mock with disabled device."""

    binary_sensor_devices = [DisabledBinarySensorMock()]
    devices = {"Test": DisabledBinarySensorMock()}
