"""The sensor tests for the QNAP QSW platform."""

from unittest.mock import patch

from aioqsw.const import API_ERROR_CODE, API_ERROR_MESSAGE, API_RESULT, API_VERSION

from homeassistant.components.update import (
    ATTR_BACKUP,
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .util import (
    FIRMWARE_INFO_MOCK,
    FIRMWARE_UPDATE_CHECK_MOCK,
    USERS_VERIFICATION_MOCK,
    async_init_integration,
)

FIRMWARE_UPDATE_LIVE_MOCK = {
    API_ERROR_CODE: 200,
    API_ERROR_MESSAGE: "OK",
    API_RESULT: "None",
}


async def test_qnap_qsw_update(hass: HomeAssistant) -> None:
    """Test creation of update entities."""

    await async_init_integration(hass)

    update = hass.states.get("update.qsw_m408_4c_firmware")
    assert update is not None
    assert update.state == STATE_ON
    assert (
        update.attributes[ATTR_INSTALLED_VERSION]
        == FIRMWARE_INFO_MOCK[API_RESULT][API_VERSION]
    )
    assert (
        update.attributes[ATTR_LATEST_VERSION]
        == FIRMWARE_UPDATE_CHECK_MOCK[API_RESULT][API_VERSION]
    )
    assert update.attributes[ATTR_IN_PROGRESS] is False

    with (
        patch(
            "homeassistant.components.qnap_qsw.QnapQswApi.get_firmware_update_check",
            return_value=FIRMWARE_UPDATE_CHECK_MOCK,
        ) as mock_firmware_update_check,
        patch(
            "homeassistant.components.qnap_qsw.QnapQswApi.get_users_verification",
            return_value=USERS_VERIFICATION_MOCK,
        ) as mock_users_verification,
        patch(
            "homeassistant.components.qnap_qsw.QnapQswApi.post_firmware_update_live",
            return_value=FIRMWARE_UPDATE_LIVE_MOCK,
        ) as mock_firmware_update_live,
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_BACKUP: False,
                ATTR_ENTITY_ID: "update.qsw_m408_4c_firmware",
            },
            blocking=True,
        )

        mock_firmware_update_check.assert_called_once()
        mock_firmware_update_live.assert_called_once()
        mock_users_verification.assert_called()

    update = hass.states.get("update.qsw_m408_4c_firmware")
    assert update is not None
    assert update.state == STATE_OFF
    assert (
        update.attributes[ATTR_INSTALLED_VERSION]
        == FIRMWARE_UPDATE_CHECK_MOCK[API_RESULT][API_VERSION]
    )
    assert (
        update.attributes[ATTR_LATEST_VERSION]
        == FIRMWARE_UPDATE_CHECK_MOCK[API_RESULT][API_VERSION]
    )
    assert update.attributes[ATTR_IN_PROGRESS] is False
