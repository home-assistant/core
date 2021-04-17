"""Tests for the AVM Fritz!Box integration."""
from unittest import mock
from unittest.mock import Mock

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_PASSWORD: "fake_pass",
                CONF_USERNAME: "fake_user",
            }
        ]
    }
}


class FritzConnectionMock:  # pylint: disable=too-few-public-methods
    """FritzConnection mocking."""

    FRITZBOX_DATA = {
        ("WANIPConn:1", "GetStatusInfo"): {
            "NewConnectionStatus": "Connected",
            "NewUptime": 35307,
        },
        ("WANIPConnection:1", "GetStatusInfo"): {},
        ("WANCommonIFC:1", "GetCommonLinkProperties"): {
            "NewLayer1DownstreamMaxBitRate": 10087000,
            "NewLayer1UpstreamMaxBitRate": 2105000,
            "NewPhysicalLinkStatus": "Up",
        },
        ("WANCommonIFC:1", "GetAddonInfos"): {
            "NewByteSendRate": 3438,
            "NewByteReceiveRate": 67649,
            "NewTotalBytesSent": 1712232562,
            "NewTotalBytesReceived": 5221019883,
        },
        ("LANEthernetInterfaceConfig:1", "GetStatistics"): {
            "NewBytesSent": 23004321,
            "NewBytesReceived": 12045,
        },
    }
    FRITZBOX_DATA_INDEXED = {
        ("X_AVM-DE_Homeauto:1", "GetGenericDeviceInfos"): [
            {
                "NewSwitchIsValid": "VALID",
                "NewMultimeterIsValid": "VALID",
                "NewTemperatureIsValid": "VALID",
                "NewDeviceId": 16,
                "NewAIN": "08761 0114116",
                "NewDeviceName": "FRITZ!DECT 200 #1",
                "NewTemperatureOffset": "0",
                "NewSwitchLock": "0",
                "NewProductName": "FRITZ!DECT 200",
                "NewPresent": "CONNECTED",
                "NewMultimeterPower": 1673,
                "NewHkrComfortTemperature": "0",
                "NewSwitchMode": "AUTO",
                "NewManufacturer": "AVM",
                "NewMultimeterIsEnabled": "ENABLED",
                "NewHkrIsTemperature": "0",
                "NewFunctionBitMask": 2944,
                "NewTemperatureIsEnabled": "ENABLED",
                "NewSwitchState": "ON",
                "NewSwitchIsEnabled": "ENABLED",
                "NewFirmwareVersion": "03.87",
                "NewHkrSetVentilStatus": "CLOSED",
                "NewMultimeterEnergy": 5182,
                "NewHkrComfortVentilStatus": "CLOSED",
                "NewHkrReduceTemperature": "0",
                "NewHkrReduceVentilStatus": "CLOSED",
                "NewHkrIsEnabled": "DISABLED",
                "NewHkrSetTemperature": "0",
                "NewTemperatureCelsius": "225",
                "NewHkrIsValid": "INVALID",
            },
            {},
        ]
    }

    MODELNAME = "FRITZ!Box 7490"

    def __init__(self):
        """Inint Mocking class."""
        type(self).modelname = mock.PropertyMock(return_value=self.MODELNAME)
        self.call_action = mock.Mock(side_effect=self._side_effect_callaction)
        type(self).actionnames = mock.PropertyMock(
            side_effect=self._side_effect_actionnames
        )
        services = {
            srv: None
            for srv, _ in list(self.FRITZBOX_DATA.keys())
            + list(self.FRITZBOX_DATA_INDEXED.keys())
        }
        type(self).services = mock.PropertyMock(side_effect=[services])

    def _side_effect_callaction(self, service, action, **kwargs):
        if kwargs:
            index = next(iter(kwargs.values()))
            return self.FRITZBOX_DATA_INDEXED[(service, action)][index]

        return self.FRITZBOX_DATA[(service, action)]

    def _side_effect_actionnames(self):
        return list(self.FRITZBOX_DATA.keys()) + list(self.FRITZBOX_DATA_INDEXED.keys())


class FritzDeviceBinarySensorMock(Mock):
    """Mock of a AVM Fritz!Box binary sensor device."""

    ain = "fake_ain"
    alert_state = "fake_state"
    fw_version = "1.2.3"
    has_alarm = True
    has_switch = False
    has_temperature_sensor = False
    has_thermostat = False
    manufacturer = "fake_manufacturer"
    name = "fake_name"
    present = True
    productname = "fake_productname"


class FritzDeviceClimateMock(Mock):
    """Mock of a AVM Fritz!Box climate device."""

    actual_temperature = 18.0
    ain = "fake_ain"
    alert_state = "fake_state"
    battery_level = 23
    battery_low = True
    comfort_temperature = 22.0
    device_lock = "fake_locked_device"
    eco_temperature = 16.0
    fw_version = "1.2.3"
    has_alarm = False
    has_switch = False
    has_temperature_sensor = False
    has_thermostat = True
    holiday_active = "fake_holiday"
    lock = "fake_locked"
    manufacturer = "fake_manufacturer"
    name = "fake_name"
    present = True
    productname = "fake_productname"
    summer_active = "fake_summer"
    target_temperature = 19.5
    window_open = "fake_window"


class FritzDeviceSensorMock(Mock):
    """Mock of a AVM Fritz!Box sensor device."""

    ain = "fake_ain"
    device_lock = "fake_locked_device"
    fw_version = "1.2.3"
    has_alarm = False
    has_switch = False
    has_temperature_sensor = True
    has_thermostat = False
    lock = "fake_locked"
    manufacturer = "fake_manufacturer"
    name = "fake_name"
    present = True
    productname = "fake_productname"
    temperature = 1.23


class FritzDeviceSwitchMock(Mock):
    """Mock of a AVM Fritz!Box switch device."""

    ain = "fake_ain"
    device_lock = "fake_locked_device"
    energy = 1234
    fw_version = "1.2.3"
    has_alarm = False
    has_switch = True
    has_temperature_sensor = True
    has_thermostat = False
    switch_state = "fake_state"
    lock = "fake_locked"
    manufacturer = "fake_manufacturer"
    name = "fake_name"
    power = 5678
    present = True
    productname = "fake_productname"
    temperature = 135
