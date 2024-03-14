"""The test for the Facebook notify module."""

import base64
from http import HTTPStatus
import logging
from unittest.mock import patch

import pytest
import requests_mock

from homeassistant.components import notify
import homeassistant.components.clicksend_tts.notify as cs_tts
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

# Infos from https://developers.clicksend.com/docs/rest/v3/#testing
TEST_USERNAME = "nocredit"
TEST_API_KEY = "D83DED51-9E35-4D42-9BB9-0E34B7CA85AE"
TEST_VOICE_NUMBER = "+61411111111"

TEST_VOICE = "male"
TEST_LANGUAGE = "fr-fr"
TEST_MESSAGE = "Just a test message!"


CONFIG = {
    notify.DOMAIN: {
        "platform": "clicksend_tts",
        cs_tts.CONF_USERNAME: TEST_USERNAME,
        cs_tts.CONF_API_KEY: TEST_API_KEY,
        cs_tts.CONF_RECIPIENT: TEST_VOICE_NUMBER,
        cs_tts.CONF_LANGUAGE: TEST_LANGUAGE,
        cs_tts.CONF_VOICE: TEST_VOICE,
    }
}


@pytest.fixture
def mock_clicksend_tts_notify():
    """Mock Clicksend TTS notify service."""
    with patch(
        "homeassistant.components.clicksend_tts.notify.get_service", autospec=True
    ) as ns:
        yield ns


async def setup_notify(hass):
    """Test setup."""
    with assert_setup_component(1, notify.DOMAIN) as config:
        assert await async_setup_component(hass, notify.DOMAIN, CONFIG)
        assert config[notify.DOMAIN]
        await hass.async_block_till_done()


async def test_no_notify_service(
    hass: HomeAssistant, mock_clicksend_tts_notify, caplog: pytest.LogCaptureFixture
) -> None:
    """Test missing platform notify service instance."""
    caplog.set_level(logging.ERROR)
    mock_clicksend_tts_notify.return_value = None
    await setup_notify(hass)
    await hass.async_block_till_done()
    assert mock_clicksend_tts_notify.called
    assert "Failed to initialize notification service clicksend_tts" in caplog.text


async def test_send_simple_message(hass: HomeAssistant) -> None:
    """Test sending a simple message with success."""

    with requests_mock.Mocker() as mock:
        # Mocking authentication endpoint
        mock.get(
            f"{cs_tts.BASE_API_URL}/account",
            status_code=HTTPStatus.OK,
        )

        # Mocking TTS endpoint
        mock.post(
            f"{cs_tts.BASE_API_URL}/voice/send",
            status_code=HTTPStatus.OK,
        )

        # Setting up integration
        await setup_notify(hass)

        # Sending message
        data = {
            notify.ATTR_MESSAGE: TEST_MESSAGE,
        }
        await hass.services.async_call(
            notify.DOMAIN, cs_tts.DEFAULT_NAME, data, blocking=True
        )

        # Checking if everything went well
        assert mock.called
        assert mock.call_count == 2

        expected_body = {
            "messages": [
                {
                    "source": "hass.notify",
                    "to": TEST_VOICE_NUMBER,
                    "body": TEST_MESSAGE,
                    "lang": TEST_LANGUAGE,
                    "voice": TEST_VOICE,
                }
            ]
        }
        assert mock.last_request.json() == expected_body

        expected_content_type = "application/json"
        assert (
            "Content-Type" in mock.last_request.headers
            and mock.last_request.headers["Content-Type"] == expected_content_type
        )

        encoded_auth = base64.b64encode(
            f"{TEST_USERNAME}:{TEST_API_KEY}".encode()
        ).decode()
        expected_auth = f"Basic {encoded_auth}"
        assert (
            "Authorization" in mock.last_request.headers
            and mock.last_request.headers["Authorization"] == expected_auth
        )
