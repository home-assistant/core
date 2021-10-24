"""Tests for the QNAP QSW integration."""

import requests_mock

from homeassistant.components.qnap_qsw import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

CONFIG = {
    CONF_HOST: "192.168.1.200",
    CONF_PASSWORD: "pass",
    CONF_USERNAME: "admin",
}


def qnap_qsw_requests_mock(mock):
    """Mock requests performed to QNAP QSW API."""

    firmware_condition_fixture = "qnap_qsw/firmware-condition.json"
    firmware_info_fixture = "qnap_qsw/firmware-info.json"
    firmware_update_check_fixture = "qnap_qsw/firmware-update-check.json"
    system_board_fixture = "qnap_qsw/system-board.json"
    system_command_reboot_fixture = "qnap_qsw/system-command-reboot.json"
    system_sensor_fixture = "qnap_qsw/system-sensor.json"
    system_time_fixture = "qnap_qsw/system-time.json"
    users_exit_fixture = "qnap_qsw/users-exit.json"
    users_login_fixture = "qnap_qsw/users-login.json"

    mock.get(
        "http://192.168.1.200/api/v1/firmware/condition",
        text=load_fixture(firmware_condition_fixture),
    )
    mock.get(
        "http://192.168.1.200/api/v1/firmware/info",
        text=load_fixture(firmware_info_fixture),
    )
    mock.get(
        "http://192.168.1.200/api/v1/firmware/update/check",
        text=load_fixture(firmware_update_check_fixture),
    )
    mock.get(
        "http://192.168.1.200/api/v1/system/board",
        text=load_fixture(system_board_fixture),
    )
    mock.post(
        "http://192.168.1.200/api/v1/system/command",
        text=load_fixture(system_command_reboot_fixture),
    )
    mock.get(
        "http://192.168.1.200/api/v1/system/sensor",
        text=load_fixture(system_sensor_fixture),
    )
    mock.get(
        "http://192.168.1.200/api/v1/system/time",
        text=load_fixture(system_time_fixture),
    )
    mock.post(
        "http://192.168.1.200/api/v1/users/exit",
        text=load_fixture(users_exit_fixture),
    )
    mock.post(
        "http://192.168.1.200/api/v1/users/login",
        text=load_fixture(users_login_fixture),
    )


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
):
    """Set up the QNAP QSW integration in Home Assistant."""

    with requests_mock.mock() as _m:
        qnap_qsw_requests_mock(_m)

        entry = MockConfigEntry(domain=DOMAIN, data=CONFIG)
        entry.add_to_hass(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
