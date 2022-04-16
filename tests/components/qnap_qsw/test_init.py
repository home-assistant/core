"""Define tests for the QNAP QSW init."""

from unittest.mock import patch

from homeassistant.components.qnap_qsw.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .util import (
    CONFIG,
    FIRMWARE_CONDITION_MOCK,
    FIRMWARE_INFO_MOCK,
    SYSTEM_BOARD_MOCK,
    SYSTEM_SENSOR_MOCK,
    SYSTEM_TIME_MOCK,
    USERS_LOGIN_MOCK,
)

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="qsw_unique_id", data=CONFIG
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
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
