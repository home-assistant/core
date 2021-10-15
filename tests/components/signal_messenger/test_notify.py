"""The tests for the signal_messenger platform."""

import logging
import os
import tempfile
from unittest.mock import patch

from homeassistant.setup import async_setup_component

BASE_COMPONENT = "notify"


async def test_signal_messenger_init(hass):
    config = {
        BASE_COMPONENT: {
            "name": "test",
            "platform": "signal_messenger",
            "url": "http://127.0.0.1:8080",
            "number": "+43443434343",
            "recipients": ["+435565656565"],
        }
    }

    with patch("pysignalclirestapi.SignalCliRestApi.send_message", return_value=None):
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        assert hass.services.has_service(BASE_COMPONENT, "test")


def test_send_message(signal_notification_service, signal_requests_mock, caplog):
    message = "Testing Signal Messenger platform :)"
    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
    ):
        signal_notification_service.send_message(message)
    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2


def test_send_message_should_show_deprecation_warning(
    signal_notification_service, signal_requests_mock, caplog
):
    message = "Testing Signal Messenger platform with attachment :)"
    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.signal_messenger.notify"
    ):
        with tempfile.NamedTemporaryFile(
            suffix=".png", prefix=os.path.basename(__file__)
        ) as tf:
            data = {"data": {"attachment": tf.name}}
            signal_notification_service.send_message(message, **data)
    assert (
        "The 'attachment' option is deprecated, please replace it with 'attachments'. This option will become invalid in version 0.108"
        in caplog.text
    )
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2


def test_send_message_with_attachment(
    signal_notification_service, signal_requests_mock, caplog
):
    message = "Testing Signal Messenger platform :)"
    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
    ):
        with tempfile.NamedTemporaryFile(
            suffix=".png", prefix=os.path.basename(__file__)
        ) as tf:
            data = {"data": {"attachments": [tf.name]}}
            signal_notification_service.send_message(message, **data)
    assert "Sending signal message" in caplog.text
    assert signal_requests_mock.called
    assert signal_requests_mock.call_count == 2
