"""Tests for the Airzone integration."""

from typing import Any
from unittest.mock import patch

from aioairzone_cloud.const import (
    API_ACTIVE,
    API_AZ_AIDOO,
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
    API_NAME,
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


def mock_get_device_status(device: Device) -> dict[str, Any]:
    """Mock API device status."""

    if device.get_id() == "aidoo1":
        return {
            API_ACTIVE: False,
            API_ERRORS: [],
            API_IS_CONNECTED: True,
            API_WS_CONNECTED: True,
            API_LOCAL_TEMP: {
                API_CELSIUS: 21,
                API_FAH: 70,
            },
            API_WARNINGS: [],
        }
    if device.get_id() == "system1":
        return {
            API_ERRORS: [],
            API_IS_CONNECTED: True,
            API_WS_CONNECTED: True,
            API_WARNINGS: [],
        }
    if device.get_id() == "zone1":
        return {
            API_ACTIVE: True,
            API_HUMIDITY: 30,
            API_IS_CONNECTED: True,
            API_WS_CONNECTED: True,
            API_LOCAL_TEMP: {
                API_FAH: 68,
                API_CELSIUS: 20,
            },
            API_WARNINGS: [],
        }
    if device.get_id() == "zone2":
        return {
            API_ACTIVE: False,
            API_HUMIDITY: 24,
            API_IS_CONNECTED: True,
            API_WS_CONNECTED: True,
            API_LOCAL_TEMP: {
                API_FAH: 77,
                API_CELSIUS: 25,
            },
            API_WARNINGS: [],
        }
    return None


def mock_get_webserver(webserver: WebServer, devices: bool) -> dict[str, Any]:
    """Mock API get webserver."""

    if webserver.get_id() == WS_ID_AIDOO:
        return GET_WEBSERVER_MOCK_AIDOO

    return GET_WEBSERVER_MOCK


async def async_init_integration(
    hass: HomeAssistant,
) -> None:
    """Set up the Airzone integration in Home Assistant."""

    config_entry = MockConfigEntry(
        data=CONFIG,
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
