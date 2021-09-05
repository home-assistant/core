"""Mocks for tests."""

from typing import Any
from unittest.mock import MagicMock

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl
from devolo_home_control_api.properties.binary_sensor_property import (
    BinarySensorProperty,
)
from devolo_home_control_api.properties.settings_property import SettingsProperty
from devolo_home_control_api.publisher.publisher import Publisher


class BinarySensorPropertyMock(BinarySensorProperty):
    """devolo Home Control binary sensor mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self._logger = MagicMock()
        self.element_uid = "Test"
        self.key_count = 1
        self.sensor_type = "door"
        self.sub_type = ""
        self.state = False


class SettingsMock(SettingsProperty):
    """devolo Home Control settings mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self._logger = MagicMock()
        self.name = "Test"
        self.zone = "Test"


class DeviceMock(Zwave):
    """devolo Home Control device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        self.status = 0
        self.brand = "devolo"
        self.name = "Test Device"
        self.uid = "Test"
        self.settings_property = {"general_device_settings": SettingsMock()}


class BinarySensorMock(DeviceMock):
    """devolo Home Control binary sensor device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.binary_sensor_property = {"Test": BinarySensorPropertyMock()}


class RemoteControlMock(DeviceMock):
    """devolo Home Control remote control device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.remote_control_property = {"Test": BinarySensorPropertyMock()}


class DisabledBinarySensorMock(DeviceMock):
    """devolo Home Control disabled binary sensor device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.binary_sensor_property = {
            "devolo.WarningBinaryFI:Test": BinarySensorPropertyMock()
        }


class HomeControlMock(HomeControl):
    """devolo Home Control gateway mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self.devices = {}
        self.publisher = MagicMock()

    def websocket_disconnect(self, event: str):
        """Mock disconnect of the websocket."""


class HomeControlMockBinarySensor(HomeControlMock):
    """devolo Home Control gateway mock with binary sensor device."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {"Test": BinarySensorMock()}
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class HomeControlMockRemoteControl(HomeControlMock):
    """devolo Home Control gateway mock with remote control device."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {"Test": RemoteControlMock()}
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class HomeControlMockDisabledBinarySensor(HomeControlMock):
    """devolo Home Control gateway mock with disabled device."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {"Test": DisabledBinarySensorMock()}
