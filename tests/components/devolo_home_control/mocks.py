"""Mocks for tests."""

from unittest.mock import MagicMock

from devolo_home_control_api.publisher.updater import Updater


class BinarySensorPropertyMock:
    """devolo Home Control binary sensor mock."""

    key_count = 2
    sensor_type = "door"
    sub_type = ""
    state = False


class SettingsMock:
    """devolo Home Control settings mock."""

    name = "Test"
    zone = "Test"


class DeviceMock:
    """devolo Home Control device mock."""

    brand = "devolo"
    name = "Test"
    uid = "Test"
    settings_property = {"general_device_settings": SettingsMock()}

    def is_online(self):
        """Mock online state of the device."""
        return True


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
    devices = {}
    publisher = MagicMock()

    def websocket_disconnect(self):
        """Mock disconnect of the websocket."""
        pass


class HomeControlMockBinarySensor(HomeControlMock):
    """devolo Home Control gateway mock with binary sensor device."""

    binary_sensor_devices = [BinarySensorMock()]
    devices = {"Test": BinarySensorMock()}
    updater = Updater(devices=devices, gateway=None, publisher=MagicMock())


class HomeControlMockRemoteControl(HomeControlMock):
    """devolo Home Control gateway mock with remote control device."""

    devices = {"Test": RemoteControlMock()}


class HomeControlMockDisabledBinarySensor(HomeControlMock):
    """devolo Home Control gateway mock with disabled device."""

    binary_sensor_devices = [DisabledBinarySensorMock()]
    devices = {"Test": DisabledBinarySensorMock()}
