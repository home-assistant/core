"""Define tests for the QNAP QSW coordinator."""

from unittest.mock import patch

from aioqsw.exceptions import APIError, QswError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.qnap_qsw.const import DOMAIN
from homeassistant.components.qnap_qsw.coordinator import (
    DATA_SCAN_INTERVAL,
    FW_SCAN_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .util import (
    CONFIG,
    FIRMWARE_CONDITION_MOCK,
    FIRMWARE_INFO_MOCK,
    FIRMWARE_UPDATE_CHECK_MOCK,
    LACP_INFO_MOCK,
    PORTS_STATISTICS_MOCK,
    PORTS_STATUS_MOCK,
    SYSTEM_BOARD_MOCK,
    SYSTEM_SENSOR_MOCK,
    SYSTEM_TIME_MOCK,
    USERS_LOGIN_MOCK,
    USERS_VERIFICATION_MOCK,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_client_connector_error(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test ClientConnectorError on coordinator update."""

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_firmware_condition",
        return_value=FIRMWARE_CONDITION_MOCK,
    ) as mock_firmware_condition, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_firmware_info",
        return_value=FIRMWARE_INFO_MOCK,
    ) as mock_firmware_info, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_firmware_update_check",
        return_value=FIRMWARE_UPDATE_CHECK_MOCK,
    ) as mock_firmware_update_check, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_lacp_info",
        return_value=LACP_INFO_MOCK,
    ) as mock_lacp_info, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_ports_statistics",
        return_value=PORTS_STATISTICS_MOCK,
    ) as mock_ports_statistics, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_ports_status",
        return_value=PORTS_STATUS_MOCK,
    ) as mock_ports_status, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_system_board",
        return_value=SYSTEM_BOARD_MOCK,
    ) as mock_system_board, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_system_sensor",
        return_value=SYSTEM_SENSOR_MOCK,
    ) as mock_system_sensor, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_system_time",
        return_value=SYSTEM_TIME_MOCK,
    ) as mock_system_time, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_users_verification",
        return_value=USERS_VERIFICATION_MOCK,
    ) as mock_users_verification, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.post_users_login",
        return_value=USERS_LOGIN_MOCK,
    ) as mock_users_login:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_firmware_condition.assert_called_once()
        mock_firmware_info.assert_called_once()
        mock_firmware_update_check.assert_called_once()
        mock_lacp_info.assert_called_once()
        mock_ports_statistics.assert_called_once()
        mock_ports_status.assert_called_once()
        mock_system_board.assert_called_once()
        mock_system_sensor.assert_called_once()
        mock_system_time.assert_called_once()
        mock_users_verification.assert_called_once()
        mock_users_login.assert_called_once()

        mock_firmware_condition.reset_mock()
        mock_firmware_info.reset_mock()
        mock_firmware_update_check.reset_mock()
        mock_lacp_info.reset_mock()
        mock_ports_statistics.reset_mock()
        mock_ports_status.reset_mock()
        mock_system_board.reset_mock()
        mock_system_sensor.reset_mock()
        mock_system_time.reset_mock()
        mock_users_verification.reset_mock()
        mock_users_login.reset_mock()

        mock_system_sensor.side_effect = QswError
        freezer.tick(DATA_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        mock_system_sensor.assert_called_once()
        mock_users_verification.assert_called()
        mock_users_login.assert_not_called()

        state = hass.states.get("sensor.qsw_m408_4c_temperature")
        assert state.state == STATE_UNAVAILABLE

        mock_firmware_update_check.side_effect = APIError
        freezer.tick(FW_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        mock_firmware_update_check.assert_called_once()
        mock_firmware_update_check.reset_mock()

        mock_firmware_update_check.side_effect = QswError
        freezer.tick(FW_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        mock_firmware_update_check.assert_called_once()

        update = hass.states.get("update.qsw_m408_4c_firmware_update")
        assert update.state == STATE_UNAVAILABLE
