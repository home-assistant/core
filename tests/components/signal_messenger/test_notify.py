"""The tests for the signal_messenger platform."""

import logging
import os
import tempfile

from pysignalclirestapi import SignalCliRestApi

import homeassistant.components.signal_messenger.notify as signalmessenger
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

BASE_COMPONENT = "notify"


async def test_signal_messenger_init(hass):
    """Test that service loads successfully."""

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

        # Test that service loads successfully
        assert hass.services.has_service(BASE_COMPONENT, "test")


class TestSignalMessenger:
    """Test the signal_messenger notify."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        recipients = ["+435565656565"]
        number = "+43443434343"
        client = SignalCliRestApi("http://127.0.0.1:8080", number)
        self._signalmessenger = signalmessenger.SignalNotificationService(
            recipients, client
        )

    def test_send_message(self, requests_mock, caplog):
        """Test send message."""

        self.setUp()

        message = "Testing Signal Messenger platform :)"
        requests_mock.register_uri(
            "POST",
            "http://127.0.0.1:8080/v2/send",
            status_code=201,
        )
        requests_mock.register_uri(
            "GET",
            "http://127.0.0.1:8080/v1/about",
            status_code=200,
            json={"versions": ["v1", "v2"]},
        )
        with caplog.at_level(
            logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
        ):
            self._signalmessenger.send_message(message)
        assert "Sending signal message" in caplog.text
        assert requests_mock.called is True
        assert requests_mock.call_count == 2

    def test_send_message_should_show_deprecation_warning(self, requests_mock, caplog):
        """Test send message."""

        self.setUp()

        message = "Testing Signal Messenger platform with attachment :)"
        requests_mock.register_uri(
            "POST",
            "http://127.0.0.1:8080/v2/send",
            status_code=201,
        )
        requests_mock.register_uri(
            "GET",
            "http://127.0.0.1:8080/v1/about",
            status_code=200,
            json={"versions": ["v1", "v2"]},
        )
        with caplog.at_level(
            logging.WARNING, logger="homeassistant.components.signal_messenger.notify"
        ):
            with tempfile.NamedTemporaryFile(
                suffix=".png", prefix=os.path.basename(__file__)
            ) as tf:
                data = {"data": {"attachment": tf.name}}
                self._signalmessenger.send_message(message, **data)
        assert (
            "The 'attachment' option is deprecated, please replace it with 'attachments'. This option will become invalid in version 0.108"
            in caplog.text
        )
        assert requests_mock.called is True
        assert requests_mock.call_count == 2

    def test_send_message_with_attachment(self, requests_mock, caplog):
        """Test send message."""

        self.setUp()

        message = "Testing Signal Messenger platform :)"
        requests_mock.register_uri(
            "POST",
            "http://127.0.0.1:8080/v2/send",
            status_code=201,
        )
        requests_mock.register_uri(
            "GET",
            "http://127.0.0.1:8080/v1/about",
            status_code=200,
            json={"versions": ["v1", "v2"]},
        )
        with caplog.at_level(
            logging.DEBUG, logger="homeassistant.components.signal_messenger.notify"
        ):
            with tempfile.NamedTemporaryFile(
                suffix=".png", prefix=os.path.basename(__file__)
            ) as tf:
                data = {"data": {"attachments": [tf.name]}}
                self._signalmessenger.send_message(message, **data)
        assert "Sending signal message" in caplog.text
        assert requests_mock.called is True
        assert requests_mock.call_count == 2
