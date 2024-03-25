"""Test the SIP Call config flow."""
import logging

import pytest

from homeassistant.components.sipcall.notify import SIPCallNotificationService


async def test_send_message_without_target_logs_error(
    sipcall_notification_service: SIPCallNotificationService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test send message without target."""
    with caplog.at_level(
        logging.ERROR, logger="homeassistant.components.sipcall.notify"
    ):
        await sipcall_notification_service.async_send_message("dummy message")
    assert "sipcall require a 'target'" in caplog.text


async def test_sipcall(
    mock_async_call_and_cancel, sipcall_notification_service: SIPCallNotificationService
) -> None:
    """Test send message."""

    await sipcall_notification_service.async_send_message(
        message="dummy message", target="1234", data={"duration": 11}
    )

    # Ensure that async_call_and_cancel was called exactly once
    mock_async_call_and_cancel.assert_called_once()

    # Check it was called with the correct args
    args, kwargs = mock_async_call_and_cancel.call_args
    invite, duration = args

    assert duration == 11
    assert invite.uri_from == "sip:myuser@mysipdomain.com"
    assert invite.uri_to == "sip:1234@mysipserver.com"
    assert invite.uri_via == "mysipserver.com"
