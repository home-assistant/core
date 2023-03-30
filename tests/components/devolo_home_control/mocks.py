"""Mocks for tests."""

from typing import Any
from unittest.mock import MagicMock

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl
from devolo_home_control_api.properties.binary_sensor_property import (
    BinarySensorProperty,
)
from devolo_home_control_api.properties.binary_switch_property import (
    BinarySwitchProperty,
)
from devolo_home_control_api.properties.consumption_property import ConsumptionProperty
from devolo_home_control_api.properties.multi_level_sensor_property import (
    MultiLevelSensorProperty,
)
from devolo_home_control_api.properties.multi_level_switch_property import (
    MultiLevelSwitchProperty,
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


class BinarySwitchPropertyMock(BinarySwitchProperty):
    """devolo Home Control binary sensor mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self._logger = MagicMock()
        self.element_uid = "Test"
        self.state = False


class ConsumptionPropertyMock(ConsumptionProperty):
    """devolo Home Control binary sensor mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self._logger = MagicMock()
        self.element_uid = "devolo.Meter:Test"
        self.current_unit = "W"
        self.total_unit = "kWh"
        self._current = 0.0
        self._total = 0.0


class MultiLevelSensorPropertyMock(MultiLevelSensorProperty):
    """devolo Home Control multi level sensor mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self.element_uid = "Test"
        self.sensor_type = "temperature"
        self._unit = "°C"
        self._value = 20
        self._logger = MagicMock()


class MultiLevelSwitchPropertyMock(MultiLevelSwitchProperty):
    """devolo Home Control multi level switch mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self.element_uid = "Test"
        self.min = 4
        self.max = 24
        self._value = 20
        self._logger = MagicMock()


class SirenPropertyMock(MultiLevelSwitchProperty):
    """devolo Home Control siren mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self.element_uid = "Test"
        self.max = 0
        self.min = 0
        self.switch_type = "tone"
        self._value = 0
        self._logger = MagicMock()


class SettingsMock(SettingsProperty):
    """devolo Home Control settings mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self._logger = MagicMock()
        self.name = "Test"
        self.zone = "Test"
        self.tone = 1


class DeviceMock(Zwave):
    """devolo Home Control device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        self.status = 0
        self.brand = "devolo"
        self.name = "Test Device"
        self.uid = "Test"
        self.settings_property = {"general_device_settings": SettingsMock()}
        self.href = "https://www.mydevolo.com"


class BinarySensorMock(DeviceMock):
    """devolo Home Control binary sensor device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.binary_sensor_property = {"Test": BinarySensorPropertyMock()}


class BinarySensorMockOverload(DeviceMock):
    """devolo Home Control disabled binary sensor device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.binary_sensor_property = {"Overload": BinarySensorPropertyMock()}
        self.binary_sensor_property["Overload"].sensor_type = "overload"


class ClimateMock(DeviceMock):
    """devolo Home Control climate device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.device_model_uid = "devolo.model.Room:Thermostat"
        self.multi_level_switch_property = {"Test": MultiLevelSwitchPropertyMock()}
        self.multi_level_switch_property["Test"].switch_type = "temperature"
        self.multi_level_sensor_property = {"Test": MultiLevelSensorPropertyMock()}


class ConsumptionMock(DeviceMock):
    """devolo Home Control meter device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()

        self.consumption_property = {"devolo.Meter:Test": ConsumptionPropertyMock()}
        self.multi_level_sensor_property = {
            "devolo.VoltageMultiLevelSensor:Test": MultiLevelSensorPropertyMock()
        }


class CoverMock(DeviceMock):
    """devolo Home Control cover device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.multi_level_switch_property = {
            "devolo.Blinds": MultiLevelSwitchPropertyMock()
        }


class LightMock(DeviceMock):
    """devolo Home Control light device mock."""

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


class SirenMock(DeviceMock):
    """devolo Home Control siren device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.device_model_uid = "devolo.model.Siren"
        self.multi_level_switch_property = {
            "devolo.SirenMultiLevelSwitch:Test": SirenPropertyMock()
        }
        self.settings_property["tone"] = SettingsMock()


class SensorMock(DeviceMock):
    """devolo Home Control sensor device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.multi_level_sensor_property = {
            "devolo.MultiLevelSensor:Test": MultiLevelSensorPropertyMock()
        }


class SwitchMock(DeviceMock):
    """devolo Home Control switch device mock."""

    def __init__(self) -> None:
        """Initialize the mock."""
        super().__init__()
        self.binary_switch_property = {
            "devolo.BinarySwitch:Test": BinarySwitchPropertyMock()
        }


class HomeControlMock(HomeControl):
    """devolo Home Control gateway mock."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        self.devices = {}
        self.publisher = MagicMock()

    def websocket_disconnect(self, event: str = "") -> None:
        """Mock disconnect of the websocket."""


class HomeControlMockBinarySensor(HomeControlMock):
    """devolo Home Control gateway mock with binary sensor devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": BinarySensorMock(),
            "Overload": BinarySensorMockOverload(),
        }
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class HomeControlMockClimate(HomeControlMock):
    """devolo Home Control gateway mock with climate devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": ClimateMock(),
        }
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class HomeControlMockConsumption(HomeControlMock):
    """devolo Home Control gateway mock with meter devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": ConsumptionMock(),
        }
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class HomeControlMockCover(HomeControlMock):
    """devolo Home Control gateway mock with cover devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": CoverMock(),
        }
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class HomeControlMockLight(HomeControlMock):
    """devolo Home Control gateway mock with light devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": LightMock(),
        }
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


class HomeControlMockSensor(HomeControlMock):
    """devolo Home Control gateway mock with sensor devices."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {
            "Test": SensorMock(),
        }
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class HomeControlMockSiren(HomeControlMock):
    """devolo Home Control gateway mock with siren device."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {"Test": SirenMock()}
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()


class HomeControlMockSwitch(HomeControlMock):
    """devolo Home Control gateway mock with switch device."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the mock."""
        super().__init__()
        self.devices = {"Test": SwitchMock()}
        self.publisher = Publisher(self.devices.keys())
        self.publisher.unregister = MagicMock()
