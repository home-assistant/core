"""The sensor tests for the QNAP QSW platform."""

from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .util import SYSTEM_COMMAND_MOCK, USERS_VERIFICATION_MOCK, async_init_integration


async def test_qnap_buttons(hass: HomeAssistant) -> None:
    """Test buttons."""

    await async_init_integration(hass)

    state = hass.states.get("button.qsw_m408_4c_reboot")
    assert state
    assert state.state == STATE_UNKNOWN

    with patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_users_verification",
        return_value=USERS_VERIFICATION_MOCK,
    ) as mock_users_verification, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.post_system_command",
        return_value=SYSTEM_COMMAND_MOCK,
    ) as mock_post_system_command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.qsw_m408_4c_reboot"},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_users_verification.assert_called_once()
        mock_post_system_command.assert_called_once()
