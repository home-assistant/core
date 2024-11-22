"""Test the SMS Gateway."""

from unittest.mock import MagicMock

from homeassistant.components.sms.gateway import Gateway
from homeassistant.core import HomeAssistant

from .const import (
    NEXT_SMS_MULTIPLE_1,
    NEXT_SMS_MULTIPLE_2,
    NEXT_SMS_SINGLE,
    SMS_STATUS_MULTIPLE,
    SMS_STATUS_SINGLE,
)


async def test_get_and_delete_all_sms_single_message(hass: HomeAssistant) -> None:
    """Test that a single message produces a list of entries containing the single message."""

    # Mock the Gammu state_machine
    state_machine = MagicMock()
    state_machine.GetSMSStatus = MagicMock(return_value=SMS_STATUS_SINGLE)
    state_machine.GetNextSMS = MagicMock(return_value=NEXT_SMS_SINGLE)
    state_machine.DeleteSMS = MagicMock()

    response = Gateway({"Connection": None}, hass).get_and_delete_all_sms(state_machine)

    # Assert the length of the list
    assert len(response) == 1
    assert len(response[0]) == 1

    # Assert the content of the message
    assert response[0][0]["Text"] == "Short message"


async def test_get_and_delete_all_sms_two_part_message(hass: HomeAssistant) -> None:
    """Test that a two-part message produces a list of entries containing one combined message."""

    state_machine = MagicMock()
    state_machine.GetSMSStatus = MagicMock(return_value=SMS_STATUS_MULTIPLE)
    state_machine.GetNextSMS = MagicMock(
        side_effect=iter([NEXT_SMS_MULTIPLE_1, NEXT_SMS_MULTIPLE_2])
    )
    state_machine.DeleteSMS = MagicMock()

    response = Gateway({"Connection": None}, hass).get_and_delete_all_sms(state_machine)

    assert len(response) == 1
    assert len(response[0]) == 2

    assert response[0][0]["Text"] == NEXT_SMS_MULTIPLE_1[0]["Text"]
    assert response[0][1]["Text"] == NEXT_SMS_MULTIPLE_2[0]["Text"]
