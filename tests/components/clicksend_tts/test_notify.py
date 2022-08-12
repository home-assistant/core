"""The test for the Facebook notify module."""
import base64
from http import HTTPStatus

import pytest
import requests_mock

import homeassistant.components.clicksend_tts.notify as cs_tts

# Infos from https://developers.clicksend.com/docs/rest/v3/#testing
TEST_USERNAME = "nocredit"
TEST_API_KEY = "D83DED51-9E35-4D42-9BB9-0E34B7CA85AE"
TEST_VOICE_NUMBER = "+61411111111"

TEST_VOICE = "male"
TEST_LANGUAGE = "fr-fr"
TEST_MESSAGE = "Just a test message!"


@pytest.fixture
def cs_tts_test_config():
    """Fixture for a test config of ClickSend TTS."""
    return {
        cs_tts.CONF_USERNAME: TEST_USERNAME,
        cs_tts.CONF_API_KEY: TEST_API_KEY,
        cs_tts.CONF_RECIPIENT: TEST_VOICE_NUMBER,
        cs_tts.CONF_LANGUAGE: TEST_LANGUAGE,
        cs_tts.CONF_VOICE: TEST_VOICE,
    }


@pytest.fixture
def clicksend_tts(cs_tts_test_config):
    """Fixture for ClickSend TTS."""
    return cs_tts.ClicksendNotificationService(cs_tts_test_config)


async def test_send_simple_message(hass, clicksend_tts):
    """Test sending a simple message with success."""
    with requests_mock.Mocker() as mock:
        url = f"{cs_tts.BASE_API_URL}/voice/send"
        mock.register_uri(
            requests_mock.POST,
            url,
            status_code=HTTPStatus.OK,
        )

        clicksend_tts.send_message(message=TEST_MESSAGE)
        assert mock.called
        assert mock.call_count == 1

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
            "Content-Type" in mock.last_request.headers.keys()
            and mock.last_request.headers["Content-Type"] == expected_content_type
        )

        encoded_auth = base64.b64encode(
            f"{TEST_USERNAME}:{TEST_API_KEY}".encode()
        ).decode()
        expected_auth = f"Basic {encoded_auth}"
        assert (
            "Authorization" in mock.last_request.headers.keys()
            and mock.last_request.headers["Authorization"] == expected_auth
        )
