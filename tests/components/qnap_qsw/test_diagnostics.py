"""The diagnostics tests for the QNAP QSW platform."""

from aiohttp import ClientSession
from aioqsw.const import (
    API_ANOMALY,
    API_BUILD_NUMBER,
    API_FAN1_SPEED,
    API_MAX_SWITCH_TEMP,
    API_NUMBER,
    API_PRODUCT,
    API_RESULT,
    API_SWITCH_TEMP,
    API_UPTIME,
    API_VERSION,
    QSD_ANOMALY,
    QSD_BUILD_NUMBER,
    QSD_FAN1_SPEED,
    QSD_FIRMWARE_CONDITION,
    QSD_FIRMWARE_INFO,
    QSD_MAC,
    QSD_NUMBER,
    QSD_PRODUCT,
    QSD_SERIAL,
    QSD_SYSTEM_BOARD,
    QSD_SYSTEM_SENSOR,
    QSD_SYSTEM_TIME,
    QSD_TEMP,
    QSD_TEMP_MAX,
    QSD_UPTIME,
    QSD_VERSION,
)

from homeassistant.components.diagnostics.const import REDACTED
from homeassistant.components.qnap_qsw.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .util import (
    CONFIG,
    FIRMWARE_CONDITION_MOCK,
    FIRMWARE_INFO_MOCK,
    SYSTEM_BOARD_MOCK,
    SYSTEM_SENSOR_MOCK,
    SYSTEM_TIME_MOCK,
    async_init_integration,
)

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_config_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSession
) -> None:
    """Test config entry diagnostics."""
    await async_init_integration(hass)
    assert hass.data[DOMAIN]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert (
        diag["config_entry"].items()
        >= {
            "data": {
                CONF_PASSWORD: REDACTED,
                CONF_URL: CONFIG[CONF_URL],
                CONF_USERNAME: REDACTED,
            },
            "domain": DOMAIN,
            "unique_id": REDACTED,
        }.items()
    )

    fw_cond_diag = diag["coord_data"][QSD_FIRMWARE_CONDITION]
    fw_cond_mock = FIRMWARE_CONDITION_MOCK[API_RESULT]
    assert (
        fw_cond_diag.items()
        >= {
            QSD_ANOMALY: fw_cond_mock[API_ANOMALY],
        }.items()
    )

    fw_info_diag = diag["coord_data"][QSD_FIRMWARE_INFO]
    fw_info_mock = FIRMWARE_INFO_MOCK[API_RESULT]
    assert (
        fw_info_diag.items()
        >= {
            QSD_BUILD_NUMBER: fw_info_mock[API_BUILD_NUMBER],
            QSD_NUMBER: fw_info_mock[API_NUMBER],
            QSD_VERSION: fw_info_mock[API_VERSION],
        }.items()
    )

    sys_board_diag = diag["coord_data"][QSD_SYSTEM_BOARD]
    sys_board_mock = SYSTEM_BOARD_MOCK[API_RESULT]
    assert (
        sys_board_diag.items()
        >= {
            QSD_MAC: REDACTED,
            QSD_PRODUCT: sys_board_mock[API_PRODUCT],
            QSD_SERIAL: REDACTED,
        }.items()
    )

    sys_sensor_diag = diag["coord_data"][QSD_SYSTEM_SENSOR]
    sys_sensor_mock = SYSTEM_SENSOR_MOCK[API_RESULT]
    assert (
        sys_sensor_diag.items()
        >= {
            QSD_FAN1_SPEED: sys_sensor_mock[API_FAN1_SPEED],
            QSD_TEMP: sys_sensor_mock[API_SWITCH_TEMP],
            QSD_TEMP_MAX: sys_sensor_mock[API_MAX_SWITCH_TEMP],
        }.items()
    )

    sys_time_diag = diag["coord_data"][QSD_SYSTEM_TIME]
    sys_time_mock = SYSTEM_TIME_MOCK[API_RESULT]
    assert (
        sys_time_diag.items()
        >= {
            QSD_UPTIME: sys_time_mock[API_UPTIME],
        }.items()
    )
