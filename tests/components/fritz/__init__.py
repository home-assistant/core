"""Tests for the AVM Fritz!Box integration."""
from unittest import mock

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_PORT: "1234",
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
        ("DeviceInfo:1", "GetInfo"): {
            "NewSerialNumber": "abcdefgh",
            "NewName": "TheName",
            "NewModelName": "FRITZ!Box 7490",
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
        ],
        ("Hosts1", "GetGenericHostEntry"): [
            {
                "NewSerialNumber": 1234,
                "NewName": "TheName",
                "NewModelName": "FRITZ!Box 7490",
            },
            {},
        ],
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
