"""Tests for the QNAP QSW integration."""

from unittest.mock import patch

from aioqsw.const import (
    API_ANOMALY,
    API_BUILD_NUMBER,
    API_CHIP_ID,
    API_CI_BRANCH,
    API_CI_COMMIT,
    API_CI_PIPELINE,
    API_COMMIT_CPSS,
    API_COMMIT_ISS,
    API_DATE,
    API_ERROR_CODE,
    API_ERROR_MESSAGE,
    API_FAN1_SPEED,
    API_FAN2_SPEED,
    API_MAC_ADDR,
    API_MAX_SWITCH_TEMP,
    API_MESSAGE,
    API_MODEL,
    API_NUMBER,
    API_PORT_NUM,
    API_PRODUCT,
    API_PUB_DATE,
    API_RESULT,
    API_SERIAL,
    API_SWITCH_TEMP,
    API_TRUNK_NUM,
    API_UPTIME,
    API_VERSION,
)

from homeassistant.components.qnap_qsw import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG = {
    CONF_URL: "http://192.168.1.100",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

LIVE_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: "None",
}

SYSTEM_BOARD_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: {
        API_MAC_ADDR: "MAC",
        API_SERIAL: "SERIAL",
        API_CHIP_ID: "ALLEYCAT3",
        API_MODEL: "M408",
        API_PORT_NUM: 12,
        API_PRODUCT: "QSW-M408-4C",
        API_TRUNK_NUM: 0,
    },
}

FIRMWARE_CONDITION_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: {
        API_ANOMALY: False,
        API_MESSAGE: "",
    },
}

FIRMWARE_INFO_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: {
        API_VERSION: "1.2.0",
        API_DATE: "20220128",
        API_PUB_DATE: "Fri, 28 Jan 2022 01:17:39 +0800",
        API_BUILD_NUMBER: "20220128",
        API_NUMBER: "29649",
        API_CI_COMMIT: "b2eb4c8ffb549995aeb4f9c4e645c6d882997c17",
        API_CI_BRANCH: "m408/codesigning",
        API_CI_PIPELINE: "9898",
        API_COMMIT_CPSS: "",
        API_COMMIT_ISS: "448a3208e5ea744c393b2580f4b9733add9c2faa",
    },
}

SYSTEM_COMMAND_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: "None",
}

SYSTEM_SENSOR_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: {
        API_FAN1_SPEED: 1991,
        API_FAN2_SPEED: -2,
        API_MAX_SWITCH_TEMP: 85,
        API_SWITCH_TEMP: 31,
    },
}

SYSTEM_TIME_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: {
        API_UPTIME: 91,
    },
}

USERS_LOGIN_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: "TOKEN",
}

USERS_VERIFICATION_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: "None",
}


async def async_init_integration(
    hass: HomeAssistant,
) -> None:
    """Set up the QNAP QSW integration in Home Assistant."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        domain=DOMAIN,
        unique_id="qsw_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_firmware_condition",
        return_value=FIRMWARE_CONDITION_MOCK,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_firmware_info",
        return_value=FIRMWARE_INFO_MOCK,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_system_board",
        return_value=SYSTEM_BOARD_MOCK,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_system_sensor",
        return_value=SYSTEM_SENSOR_MOCK,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_system_time",
        return_value=SYSTEM_TIME_MOCK,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.post_users_login",
        return_value=USERS_LOGIN_MOCK,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
