"""Mocks for tests."""

from typing import Any
from unittest.mock import MagicMock

from devolo_spencer_control_api.devices.zwave import Zwave
from devolo_spencer_control_api.spencercontrol import spencerControl
from devolo_spencer_control_api.properties.binary_sensor_property import (
    BinarySensorProperty,
)
from devolo_spencer_control_api.properties.binary_switch_property import (
    BinarySwitchProperty,
)
from devolo_spencer_control_api.properties.multi_level_sensor_property import (
    MultiLevelSensorProperty,
)
from devolo_spencer_control_api.properties.multi_level_switch_property import (
    MultiLevelSwitchProperty,
)
from devolo_spencer_control_api.properties.settings_property import SettingsProperty
from devolo_spencer_control_api.publisher.publisher import Publisher


class BinarySensorPropertyMock(BinarySensorProperty):
    """devolo spencer Control binary sensor mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self._logger = MagicMock()
        self.element_uid = "Test"
        self.key_count = 1
        self.sensor_type = "door"
        self.sub_type = ""
        self.state = False


class BinarySwitchPropertyMock(BinarySwitchProperty):
    """devolo spencer Control binary sensor mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self._logger = MagicMock()
        self.element_uid = "Test"


class MultiLevelSensorPropertyMock(MultiLevelSensorProperty):
    """devolo spencer Control multi level sensor mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self.element_uid = "Test"
        self.sensor_type = "temperature"
        self._unit = "°C"
        self._value = 20
        self._logger = MagicMock()


class MultiLevelSwitchPropertyMock(MultiLevelSwitchProperty):
    """devolo spencer Control multi level switch mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self.element_uid = "Test"
        self.min = 4
        self.max = 24
        self._value = 20
        self._logger = MagicMock()


class SirenPropertyMock(MultiLevelSwitchProperty):
    """devolo spencer Control siren mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self.element_uid = "Test"
        self.max = 0
        self.min = 0
        self.switch_type = "tone"
        self._value = 0
        self._logger = MagicMock()


class SettingsMock(SettingsProperty):
    """devolo spencer Control settings mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self._logger = MagicMock()
        self.name = "Test"
        self.zone = "Test"
        self.tone = 1


class DeviceMock(Zwave):
    """devolo spencer Control device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        self.status = 0
        self.brand = "devolo"
        self.name = "Test Device"
        self.uid = "Test"
        self.settings_property = {"general_device_settings": SettingsMock()}
        self.href = "https://www.mydevolo.com"


class BinarySensorMock(DeviceMock):
    """devolo spencer Control binary sensor device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.binary_sensor_property = {"Test": BinarySensorPropertyMock()}


class BinarySensorMockOverload(DeviceMock):
    """devolo spencer Control disabled binary sensor device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.binary_sensor_property = {"Overload": BinarySensorPropertyMock()}
        self.binary_sensor_property["Overload"].sensor_type = "overload"


class ClimateMock(DeviceMock):
    """devolo spencer Control climate device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.device_model_uid = "devolo.model.Room:Thermostat"
        self.multi_level_switch_property = {"Test": MultiLevelSwitchPropertyMock()}
        self.multi_level_switch_property["Test"].switch_type = "temperature"
        self.multi_level_sensor_property = {"Test": MultiLevelSensorPropertyMock()}


class CoverMock(DeviceMock):
    """devolo spencer Control cover device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.multi_level_switch_property = {
            "devolo.Blinds": MultiLevelSwitchPropertyMock()
        }


class LightMock(DeviceMock):
    """devolo spencer Control light device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.binary_switch_property = {}
        self.multi_level_switch_property = {
            "devolo.Dimmer:Test": MultiLevelSwitchPropertyMock()
        }
        self.multi_level_switch_property["devolo.Dimmer:Test"].switch_type = "dimmer"
        self.multi_level_switch_property[
            "devolo.Dimmer:Test"
        ].element_uid = "devolo.Dimmer:Test"


class RemoteControlMock(DeviceMock):
    """devolo spencer Control remote control device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.remote_control_property = {"Test": BinarySensorPropertyMock()}


class DisabledBinarySensorMock(DeviceMock):
    """devolo spencer Control disabled binary sensor device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.binary_sensor_property = {
            "devolo.WarningBinaryFI:Test": BinarySensorPropertyMock()
        }


class SirenMock(DeviceMock):
    """devolo spencer Control siren device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.device_model_uid = "devolo.model.Siren"
        self.multi_level_switch_property = {
            "devolo.SirenMultiLevelSwitch:Test": SirenPropertyMock()
        }
        self.settings_property["tone"] = SettingsMock()


class spencerControlMock(spencerControl):
    """devolo spencer Control gateway mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self.devices = {}
        self.publisher = MagicMock()

    def websocket_disconnect(self, event: str):
        """Mock disconnect of the websocket."""


class spencerControlMockBinarySensor(spencerControlMock):
    """devolo spencer Control gateway mock with binary sensor devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": BinarySensorMock(),
            "Overload": BinarySensorMockOverload(),
        }
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class spencerControlMockClimate(spencerControlMock):
    """devolo spencer Control gateway mock with climate devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": ClimateMock(),
        }
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class spencerControlMockCover(spencerControlMock):
    """devolo spencer Control gateway mock with cover devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": CoverMock(),
        }
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class spencerControlMockLight(spencerControlMock):
    """devolo spencer Control gateway mock with light devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": LightMock(),
        }
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class spencerControlMockRemoteControl(spencerControlMock):
    """devolo spencer Control gateway mock with remote control device."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {"Test": RemoteControlMock()}
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class spencerControlMockDisabledBinarySensor(spencerControlMock):
    """devolo spencer Control gateway mock with disabled device."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {"Test": DisabledBinarySensorMock()}


class spencerControlMockSiren(spencerControlMock):
    """devolo spencer Control gateway mock with siren device."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {"Test": SirenMock()}
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()
