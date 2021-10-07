"""Response mocks for Fronius Symo API calls."""

from homeassistant.components.fronius.sensor import (
    CONF_SCOPE,
    SCOPE_DEVICE,
    TYPE_INVERTER,
    TYPE_LOGGER_INFO,
    TYPE_POWER_FLOW,
)
from homeassistant.const import CONF_DEVICE, CONF_SENSOR_TYPE

from ..const import MOCK_HOST


class APIVersion:
    """Response for APIVersion endpoint."""

    url = f"{MOCK_HOST}/solar_api/GetAPIVersion.cgi"
    json = {
        "APIVersion": 1,
        "BaseURL": "/solar_api/v1/",
        "CompatibilityRange": "1.6-3",
    }


class InverterDevice:
    """Responses for InverterDevice endpoint."""

    solar_net_id = 1
    config = {
        CONF_SENSOR_TYPE: TYPE_INVERTER,
        CONF_SCOPE: SCOPE_DEVICE,
        CONF_DEVICE: solar_net_id,
    }
    url = (
        f"{MOCK_HOST}/solar_api/v1/"
        "GetInverterRealtimeData.cgi?Scope=Device&"
        f"DeviceId={solar_net_id}&"
        "DataCollection=CommonInverterData"
    )
    json_night = {
        "Body": {
            "Data": {
                "DAY_ENERGY": {"Unit": "Wh", "Value": 10828},
                "DeviceStatus": {
                    "ErrorCode": 307,
                    "LEDColor": 1,
                    "LEDState": 0,
                    "MgmtTimerRemainingTime": 17,
                    "StateToReset": False,
                    "StatusCode": 3,
                },
                "IDC": {"Unit": "A", "Value": 0},
                "TOTAL_ENERGY": {"Unit": "Wh", "Value": 44186900},
                "UDC": {"Unit": "V", "Value": 16},
                "YEAR_ENERGY": {"Unit": "Wh", "Value": 25507686},
            }
        },
        "Head": {
            "RequestArguments": {
                "DataCollection": "CommonInverterData",
                "DeviceClass": "Inverter",
                "DeviceId": f"{solar_net_id}",
                "Scope": "Device",
            },
            "Status": {"Code": 0, "Reason": "", "UserMessage": ""},
            "Timestamp": "2021-10-06T21:16:59+02:00",
        },
    }
    json_day = {
        "Body": {
            "Data": {
                "DAY_ENERGY": {"Unit": "Wh", "Value": 1113},
                "DeviceStatus": {
                    "ErrorCode": 0,
                    "LEDColor": 2,
                    "LEDState": 0,
                    "MgmtTimerRemainingTime": -1,
                    "StateToReset": False,
                    "StatusCode": 7,
                },
                "FAC": {"Unit": "Hz", "Value": 49.939999999999998},
                "IAC": {"Unit": "A", "Value": 5.1900000000000004},
                "IDC": {"Unit": "A", "Value": 2.1899999999999999},
                "PAC": {"Unit": "W", "Value": 1190},
                "TOTAL_ENERGY": {"Unit": "Wh", "Value": 44188000},
                "UAC": {"Unit": "V", "Value": 227.90000000000001},
                "UDC": {"Unit": "V", "Value": 518},
                "YEAR_ENERGY": {"Unit": "Wh", "Value": 25508798},
            }
        },
        "Head": {
            "RequestArguments": {
                "DataCollection": "CommonInverterData",
                "DeviceClass": "Inverter",
                "DeviceId": f"{solar_net_id}",
                "Scope": "Device",
            },
            "Status": {"Code": 0, "Reason": "", "UserMessage": ""},
            "Timestamp": "2021-10-07T10:01:17+02:00",
        },
    }


class InverterInfo:
    """Response for IncerterInfo endpoint."""

    url = f"{MOCK_HOST}/solar_api/v1/GetInverterInfo.cgi"
    json = {
        "Body": {
            "Data": {
                "1": {
                    "CustomName": "&#83;&#121;&#109;&#111;&#32;&#50;&#48;",
                    "DT": 121,
                    "ErrorCode": 0,
                    "PVPower": 23100,
                    "Show": 1,
                    "StatusCode": 7,
                    "UniqueID": "1234567",
                }
            }
        },
        "Head": {
            "RequestArguments": {},
            "Status": {"Code": 0, "Reason": "", "UserMessage": ""},
            "Timestamp": "2021-10-07T13:41:00+02:00",
        },
    }


class LoggerInfo:
    """Response for LoggerInfo endpoint."""

    config = {
        CONF_SENSOR_TYPE: TYPE_LOGGER_INFO,
    }
    url = f"{MOCK_HOST}/solar_api/v1/GetLoggerInfo.cgi"
    json = {
        "Body": {
            "LoggerInfo": {
                "CO2Factor": 0.52999997138977051,
                "CO2Unit": "kg",
                "CashCurrency": "EUR",
                "CashFactor": 0.078000001609325409,
                "DefaultLanguage": "en",
                "DeliveryFactor": 0.15000000596046448,
                "HWVersion": "2.4E",
                "PlatformID": "wilma",
                "ProductID": "fronius-datamanager-card",
                "SWVersion": "3.18.7-1",
                "TimezoneLocation": "Vienna",
                "TimezoneName": "CEST",
                "UTCOffset": 7200,
                "UniqueID": "123.4567890",
            }
        },
        "Head": {
            "RequestArguments": {},
            "Status": {"Code": 0, "Reason": "", "UserMessage": ""},
            "Timestamp": "2021-10-06T23:56:32+02:00",
        },
    }


class PowerFlow:
    """Responses for PowerFlow endpoint."""

    config = {
        CONF_SENSOR_TYPE: TYPE_POWER_FLOW,
    }
    url = f"{MOCK_HOST}/solar_api/v1/GetPowerFlowRealtimeData.fcgi"
    json_night = {
        "Body": {
            "Data": {
                "Inverters": {
                    "1": {
                        "DT": 121,
                        "E_Day": 10828,
                        "E_Total": 44186900,
                        "E_Year": 25507686,
                        "P": 0,
                    }
                },
                "Site": {
                    "E_Day": 10828,
                    "E_Total": 44186900,
                    "E_Year": 25507686,
                    "Meter_Location": "grid",
                    "Mode": "meter",
                    "P_Akku": None,
                    "P_Grid": 975.30999999999995,
                    "P_Load": -975.30999999999995,
                    "P_PV": None,
                    "rel_Autonomy": 0,
                    "rel_SelfConsumption": None,
                },
                "Version": "12",
            }
        },
        "Head": {
            "RequestArguments": {},
            "Status": {"Code": 0, "Reason": "", "UserMessage": ""},
            "Timestamp": "2021-10-06T23:49:54+02:00",
        },
    }
    json_day = {
        "Body": {
            "Data": {
                "Inverters": {
                    "1": {
                        "DT": 121,
                        "E_Day": 1101.7000732421875,
                        "E_Total": 44188000,
                        "E_Year": 25508788,
                        "P": 1111,
                    }
                },
                "Site": {
                    "E_Day": 1101.7000732421875,
                    "E_Total": 44188000,
                    "E_Year": 25508788,
                    "Meter_Location": "grid",
                    "Mode": "meter",
                    "P_Akku": None,
                    "P_Grid": 1703.74,
                    "P_Load": -2814.7399999999998,
                    "P_PV": 1111,
                    "rel_Autonomy": 39.4707859340472,
                    "rel_SelfConsumption": 100,
                },
                "Version": "12",
            }
        },
        "Head": {
            "RequestArguments": {},
            "Status": {"Code": 0, "Reason": "", "UserMessage": ""},
            "Timestamp": "2021-10-07T10:00:43+02:00",
        },
    }
