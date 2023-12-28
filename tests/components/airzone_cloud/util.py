"""Tests for the Airzone integration."""

from typing import Any
from unittest.mock import patch

from aioairzone_cloud.common import OperationMode
from aioairzone_cloud.const import (
    API_ACTIVE,
    API_AQ_ACTIVE,
    API_AQ_MODE_CONF,
    API_AQ_MODE_VALUES,
    API_AQ_PM_1,
    API_AQ_PM_2P5,
    API_AQ_PM_10,
    API_AQ_PRESENT,
    API_AQ_QUALITY,
    API_AZ_AIDOO,
    API_AZ_AIDOO_PRO,
    API_AZ_SYSTEM,
    API_AZ_ZONE,
    API_CELSIUS,
    API_CONFIG,
    API_CONNECTION_DATE,
    API_DEVICE_ID,
    API_DEVICES,
    API_DISCONNECTION_DATE,
    API_ERRORS,
    API_FAH,
    API_GROUP_ID,
    API_GROUPS,
    API_HUMIDITY,
    API_INSTALLATION_ID,
    API_INSTALLATIONS,
    API_IS_CONNECTED,
    API_LOCAL_TEMP,
    API_META,
    API_MODE,
    API_MODE_AVAIL,
    API_NAME,
    API_OLD_ID,
    API_POWER,
    API_RANGE_MAX_AIR,
    API_RANGE_MIN_AIR,
    API_RANGE_SP_MAX_AUTO_AIR,
    API_RANGE_SP_MAX_COOL_AIR,
    API_RANGE_SP_MAX_DRY_AIR,
    API_RANGE_SP_MAX_EMERHEAT_AIR,
    API_RANGE_SP_MAX_HOT_AIR,
    API_RANGE_SP_MAX_STOP_AIR,
    API_RANGE_SP_MAX_VENT_AIR,
    API_RANGE_SP_MIN_AUTO_AIR,
    API_RANGE_SP_MIN_COOL_AIR,
    API_RANGE_SP_MIN_DRY_AIR,
    API_RANGE_SP_MIN_EMERHEAT_AIR,
    API_RANGE_SP_MIN_HOT_AIR,
    API_RANGE_SP_MIN_STOP_AIR,
    API_RANGE_SP_MIN_VENT_AIR,
    API_SP_AIR_AUTO,
    API_SP_AIR_COOL,
    API_SP_AIR_DRY,
    API_SP_AIR_HEAT,
    API_SP_AIR_STOP,
    API_SP_AIR_VENT,
    API_SPEED_CONF,
    API_SPEED_TYPE,
    API_SPEED_VALUES,
    API_STAT_AP_MAC,
    API_STAT_CHANNEL,
    API_STAT_QUALITY,
    API_STAT_RSSI,
    API_STAT_SSID,
    API_STATUS,
    API_SYSTEM_NUMBER,
    API_TYPE,
    API_WARNINGS,
    API_WS_CONNECTED,
    API_WS_FW,
    API_WS_ID,
    API_WS_IDS,
    API_WS_TYPE,
    API_ZONE_NUMBER,
)
from aioairzone_cloud.device import Device
from aioairzone_cloud.webserver import WebServer

from homeassistant.components.airzone_cloud import DOMAIN
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

WS_ID = "11:22:33:44:55:66"
WS_ID_AIDOO = "11:22:33:44:55:67"
WS_ID_AIDOO_PRO = "11:22:33:44:55:68"

CONFIG = {
    CONF_ID: "inst1",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}

GET_INSTALLATION_MOCK = {
    API_GROUPS: [
        {
            API_GROUP_ID: "grp1",
            API_NAME: "Group",
            API_DEVICES: [
                {
                    API_DEVICE_ID: "system1",
                    API_TYPE: API_AZ_SYSTEM,
                    API_META: {
                        API_SYSTEM_NUMBER: 1,
                    },
                    API_WS_ID: WS_ID,
                },
                {
                    API_CONFIG: {},
                    API_DEVICE_ID: "zone1",
                    API_NAME: "Salon",
                    API_TYPE: API_AZ_ZONE,
                    API_META: {
                        API_SYSTEM_NUMBER: 1,
                        API_ZONE_NUMBER: 1,
                    },
                    API_WS_ID: WS_ID,
                },
                {
                    API_CONFIG: {},
                    API_DEVICE_ID: "zone2",
                    API_NAME: "Dormitorio",
                    API_TYPE: API_AZ_ZONE,
                    API_META: {
                        API_SYSTEM_NUMBER: 1,
                        API_ZONE_NUMBER: 2,
                    },
                    API_WS_ID: WS_ID,
                },
            ],
        },
        {
            API_GROUP_ID: "grp2",
            API_NAME: "Aidoo Group",
            API_DEVICES: [
                {
                    API_DEVICE_ID: "aidoo1",
                    API_NAME: "Bron",
                    API_TYPE: API_AZ_AIDOO,
                    API_WS_ID: WS_ID_AIDOO,
                },
            ],
        },
        {
            API_GROUP_ID: "grp3",
            API_NAME: "Aidoo Pro Group",
            API_DEVICES: [
                {
                    API_DEVICE_ID: "aidoo_pro",
                    API_NAME: "Bron Pro",
                    API_TYPE: API_AZ_AIDOO_PRO,
                    API_WS_ID: WS_ID_AIDOO_PRO,
                },
            ],
        },
    ],
}

GET_INSTALLATIONS_MOCK = {
    API_INSTALLATIONS: [
        {
            API_INSTALLATION_ID: CONFIG[CONF_ID],
            API_NAME: "House",
            API_WS_IDS: [
                WS_ID,
                WS_ID_AIDOO,
                WS_ID_AIDOO_PRO,
            ],
        },
    ],
}

GET_WEBSERVER_MOCK = {
    API_WS_TYPE: "ws_az",
    API_CONFIG: {
        API_WS_FW: "3.44",
        API_STAT_SSID: "Wifi",
        API_STAT_CHANNEL: 36,
        API_STAT_AP_MAC: "00:00:00:00:00:00",
    },
    API_STATUS: {
        API_IS_CONNECTED: True,
        API_STAT_QUALITY: 4,
        API_STAT_RSSI: -56,
        API_CONNECTION_DATE: "2023-05-07T12:55:51.000Z",
        API_DISCONNECTION_DATE: "2023-01-01T22:26:55.376Z",
    },
}

GET_WEBSERVER_MOCK_AIDOO = {
    API_WS_TYPE: "ws_aidoo",
    API_CONFIG: {
        API_WS_FW: "3.13",
        API_STAT_SSID: "Wifi",
        API_STAT_CHANNEL: 1,
        API_STAT_AP_MAC: "00:00:00:00:00:01",
    },
    API_STATUS: {
        API_IS_CONNECTED: True,
        API_STAT_QUALITY: 4,
        API_STAT_RSSI: -77,
        API_CONNECTION_DATE: "2023-05-24 17:00:52 +0200",
        API_DISCONNECTION_DATE: "2023-05-24 17:00:25 +0200",
    },
}

GET_WEBSERVER_MOCK_AIDOO_PRO = {
    API_WS_TYPE: "ws_aidoo",
    API_CONFIG: {
        API_WS_FW: "4.01",
        API_STAT_SSID: "Wifi",
        API_STAT_CHANNEL: 6,
        API_STAT_AP_MAC: "00:00:00:00:00:02",
    },
    API_STATUS: {
        API_IS_CONNECTED: True,
        API_STAT_QUALITY: 4,
        API_STAT_RSSI: -67,
        API_CONNECTION_DATE: "2023-11-05 17:00:52 +0200",
        API_DISCONNECTION_DATE: "2023-11-05 17:00:25 +0200",
    },
}


def mock_get_device_status(device: Device) -> dict[str, Any]:
    """Mock API device status."""

    if device.get_id() == "aidoo1":
        return {
            API_ACTIVE: False,
            API_ERRORS: [],
            API_MODE: OperationMode.HEATING.value,
            API_MODE_AVAIL: [
                OperationMode.AUTO.value,
                OperationMode.COOLING.value,
                OperationMode.HEATING.value,
                OperationMode.VENTILATION.value,
                OperationMode.DRY.value,
            ],
            API_SP_AIR_AUTO: {API_CELSIUS: 22, API_FAH: 72},
            API_SP_AIR_COOL: {API_CELSIUS: 22, API_FAH: 72},
            API_SP_AIR_HEAT: {API_CELSIUS: 22, API_FAH: 72},
            API_RANGE_MAX_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_AUTO_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_COOL_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_HOT_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_MIN_AIR: {API_CELSIUS: 15, API_FAH: 59},
            API_RANGE_SP_MIN_AUTO_AIR: {API_CELSIUS: 18, API_FAH: 64},
            API_RANGE_SP_MIN_COOL_AIR: {API_CELSIUS: 18, API_FAH: 64},
            API_RANGE_SP_MIN_HOT_AIR: {API_CELSIUS: 16, API_FAH: 61},
            API_POWER: False,
            API_SPEED_CONF: 6,
            API_SPEED_VALUES: [2, 4, 6],
            API_SPEED_TYPE: 0,
            API_IS_CONNECTED: True,
            API_WS_CONNECTED: True,
            API_LOCAL_TEMP: {API_CELSIUS: 21, API_FAH: 70},
            API_WARNINGS: [],
        }
    if device.get_id() == "aidoo_pro":
        return {
            API_ACTIVE: True,
            API_ERRORS: [],
            API_MODE: OperationMode.COOLING.value,
            API_MODE_AVAIL: [
                OperationMode.AUTO.value,
                OperationMode.COOLING.value,
                OperationMode.HEATING.value,
                OperationMode.VENTILATION.value,
                OperationMode.DRY.value,
            ],
            API_SP_AIR_AUTO: {API_CELSIUS: 22, API_FAH: 72},
            API_SP_AIR_COOL: {API_CELSIUS: 22, API_FAH: 72},
            API_SP_AIR_HEAT: {API_CELSIUS: 22, API_FAH: 72},
            API_RANGE_MAX_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_AUTO_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_COOL_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_HOT_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_MIN_AIR: {API_CELSIUS: 15, API_FAH: 59},
            API_RANGE_SP_MIN_AUTO_AIR: {API_CELSIUS: 18, API_FAH: 64},
            API_RANGE_SP_MIN_COOL_AIR: {API_CELSIUS: 18, API_FAH: 64},
            API_RANGE_SP_MIN_HOT_AIR: {API_CELSIUS: 16, API_FAH: 61},
            API_POWER: True,
            API_SPEED_CONF: 3,
            API_SPEED_VALUES: [0, 1, 2, 3, 4, 5],
            API_SPEED_TYPE: 0,
            API_IS_CONNECTED: True,
            API_WS_CONNECTED: True,
            API_LOCAL_TEMP: {API_CELSIUS: 20, API_FAH: 68},
            API_WARNINGS: [],
        }
    if device.get_id() == "system1":
        return {
            API_AQ_MODE_VALUES: ["off", "on", "auto"],
            API_AQ_PM_1: 3,
            API_AQ_PM_2P5: 4,
            API_AQ_PM_10: 3,
            API_AQ_PRESENT: True,
            API_AQ_QUALITY: "good",
            API_ERRORS: [
                {
                    API_OLD_ID: "error-id",
                },
            ],
            API_MODE: OperationMode.COOLING.value,
            API_MODE_AVAIL: [
                OperationMode.COOLING.value,
                OperationMode.HEATING.value,
                OperationMode.VENTILATION.value,
                OperationMode.DRY.value,
            ],
            API_IS_CONNECTED: True,
            API_WS_CONNECTED: True,
            API_WARNINGS: [],
        }
    if device.get_id() == "zone1":
        return {
            API_ACTIVE: True,
            API_AQ_ACTIVE: False,
            API_AQ_MODE_CONF: "auto",
            API_AQ_MODE_VALUES: ["off", "on", "auto"],
            API_AQ_PM_1: 3,
            API_AQ_PM_2P5: 4,
            API_AQ_PM_10: 3,
            API_AQ_PRESENT: True,
            API_AQ_QUALITY: "good",
            API_HUMIDITY: 30,
            API_MODE: OperationMode.COOLING.value,
            API_MODE_AVAIL: [
                OperationMode.COOLING.value,
                OperationMode.HEATING.value,
                OperationMode.VENTILATION.value,
                OperationMode.DRY.value,
            ],
            API_RANGE_MAX_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_COOL_AIR: {API_FAH: 86, API_CELSIUS: 30},
            API_RANGE_SP_MAX_DRY_AIR: {API_FAH: 86, API_CELSIUS: 30},
            API_RANGE_SP_MAX_EMERHEAT_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_HOT_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_STOP_AIR: {API_FAH: 86, API_CELSIUS: 30},
            API_RANGE_SP_MAX_VENT_AIR: {API_FAH: 86, API_CELSIUS: 30},
            API_RANGE_MIN_AIR: {API_CELSIUS: 15, API_FAH: 59},
            API_RANGE_SP_MIN_COOL_AIR: {API_CELSIUS: 18, API_FAH: 64},
            API_RANGE_SP_MIN_DRY_AIR: {API_CELSIUS: 18, API_FAH: 64},
            API_RANGE_SP_MIN_EMERHEAT_AIR: {API_FAH: 59, API_CELSIUS: 15},
            API_RANGE_SP_MIN_HOT_AIR: {API_FAH: 59, API_CELSIUS: 15},
            API_RANGE_SP_MIN_STOP_AIR: {API_FAH: 59, API_CELSIUS: 15},
            API_RANGE_SP_MIN_VENT_AIR: {API_FAH: 59, API_CELSIUS: 15},
            API_SP_AIR_COOL: {API_CELSIUS: 24, API_FAH: 75},
            API_SP_AIR_DRY: {API_CELSIUS: 24, API_FAH: 75},
            API_SP_AIR_HEAT: {API_CELSIUS: 20, API_FAH: 68},
            API_SP_AIR_VENT: {API_CELSIUS: 24, API_FAH: 75},
            API_SP_AIR_STOP: {API_CELSIUS: 24, API_FAH: 75},
            API_POWER: True,
            API_IS_CONNECTED: True,
            API_WS_CONNECTED: True,
            API_LOCAL_TEMP: {API_FAH: 68, API_CELSIUS: 20},
            API_WARNINGS: [],
        }
    if device.get_id() == "zone2":
        return {
            API_ACTIVE: False,
            API_AQ_ACTIVE: False,
            API_AQ_MODE_CONF: "auto",
            API_AQ_MODE_VALUES: ["off", "on", "auto"],
            API_AQ_PM_1: 3,
            API_AQ_PM_2P5: 4,
            API_AQ_PM_10: 3,
            API_AQ_PRESENT: True,
            API_AQ_QUALITY: "good",
            API_HUMIDITY: 24,
            API_MODE: OperationMode.COOLING.value,
            API_MODE_AVAIL: [],
            API_RANGE_MAX_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_COOL_AIR: {API_FAH: 86, API_CELSIUS: 30},
            API_RANGE_SP_MAX_DRY_AIR: {API_FAH: 86, API_CELSIUS: 30},
            API_RANGE_SP_MAX_EMERHEAT_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_HOT_AIR: {API_CELSIUS: 30, API_FAH: 86},
            API_RANGE_SP_MAX_STOP_AIR: {API_FAH: 86, API_CELSIUS: 30},
            API_RANGE_SP_MAX_VENT_AIR: {API_FAH: 86, API_CELSIUS: 30},
            API_RANGE_MIN_AIR: {API_CELSIUS: 15, API_FAH: 59},
            API_RANGE_SP_MIN_COOL_AIR: {API_CELSIUS: 18, API_FAH: 64},
            API_RANGE_SP_MIN_DRY_AIR: {API_CELSIUS: 18, API_FAH: 64},
            API_RANGE_SP_MIN_EMERHEAT_AIR: {API_FAH: 59, API_CELSIUS: 15},
            API_RANGE_SP_MIN_HOT_AIR: {API_FAH: 59, API_CELSIUS: 15},
            API_RANGE_SP_MIN_STOP_AIR: {API_FAH: 59, API_CELSIUS: 15},
            API_RANGE_SP_MIN_VENT_AIR: {API_FAH: 59, API_CELSIUS: 15},
            API_SP_AIR_COOL: {API_CELSIUS: 24, API_FAH: 75},
            API_SP_AIR_DRY: {API_CELSIUS: 24, API_FAH: 75},
            API_SP_AIR_HEAT: {API_CELSIUS: 20, API_FAH: 68},
            API_SP_AIR_VENT: {API_CELSIUS: 24, API_FAH: 75},
            API_SP_AIR_STOP: {API_CELSIUS: 24, API_FAH: 75},
            API_POWER: False,
            API_IS_CONNECTED: True,
            API_WS_CONNECTED: True,
            API_LOCAL_TEMP: {API_FAH: 77, API_CELSIUS: 25},
            API_WARNINGS: [],
        }
    return {}


def mock_get_webserver(webserver: WebServer, devices: bool) -> dict[str, Any]:
    """Mock API get webserver."""

    if webserver.get_id() == WS_ID:
        return GET_WEBSERVER_MOCK
    if webserver.get_id() == WS_ID_AIDOO:
        return GET_WEBSERVER_MOCK_AIDOO
    if webserver.get_id() == WS_ID_AIDOO_PRO:
        return GET_WEBSERVER_MOCK_AIDOO_PRO
    return {}


async def async_init_integration(
    hass: HomeAssistant,
) -> None:
    """Set up the Airzone integration in Home Assistant."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        entry_id="d186e31edb46d64d14b9b2f11f1ebd9f",
        domain=DOMAIN,
        unique_id=CONFIG[CONF_ID],
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_get_device_status",
        side_effect=mock_get_device_status,
    ), patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_get_installation",
        return_value=GET_INSTALLATION_MOCK,
    ), patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_get_installations",
        return_value=GET_INSTALLATIONS_MOCK,
    ), patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_get_webserver",
        side_effect=mock_get_webserver,
    ), patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.login",
        return_value=None,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
