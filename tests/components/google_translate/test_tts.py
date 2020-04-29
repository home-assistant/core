"""The tests for the Google speech platform."""
import asyncio
import os
import shutil
from unittest.mock import patch

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
import homeassistant.components.tts as tts
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant, mock_service
from tests.components.tts.test_init import mutagen_mock  # noqa: F401


class TestTTSGooglePlatform:
    """Test the Google speech component."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.url = "https://translate.google.com/translate_tts"
        self.url_param = {
            "tl": "en",
            "q": "90%25%20of%20I%20person%20is%20on%20front%20of%20your%20door.",
            "tk": 5,
            "client": "tw-ob",
            "textlen": 41,
            "total": 1,
            "idx": 0,
            "ie": "UTF-8",
        }

    def teardown_method(self):
        """Stop everything that was started."""
        default_tts = self.hass.config.path(tts.DEFAULT_CACHE_DIR)
        if os.path.isdir(default_tts):
            shutil.rmtree(default_tts)

        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        config = {tts.DOMAIN: {"platform": "google_translate"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say(self, mock_calculate, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        aioclient_mock.get(self.url, params=self.url_param, status=200, content=b"test")

        config = {tts.DOMAIN: {"platform": "google_translate"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "google_translate_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "90% of I person is on front of your door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert len(aioclient_mock.mock_calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".mp3") != -1

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say_german_config(self, mock_calculate, aioclient_mock):
        """Test service call say with german code in the config."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        self.url_param["tl"] = "de"
        aioclient_mock.get(self.url, params=self.url_param, status=200, content=b"test")

        config = {tts.DOMAIN: {"platform": "google_translate", "language": "de"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "google_translate_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "90% of I person is on front of your door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert len(aioclient_mock.mock_calls) == 1

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say_german_service(self, mock_calculate, aioclient_mock):
        """Test service call say with german code in the service."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        self.url_param["tl"] = "de"
        aioclient_mock.get(self.url, params=self.url_param, status=200, content=b"test")

        config = {
            tts.DOMAIN: {"platform": "google_translate", "service_name": "google_say"}
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "google_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "90% of I person is on front of your door.",
                tts.ATTR_LANGUAGE: "de",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert len(aioclient_mock.mock_calls) == 1

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say_error(self, mock_calculate, aioclient_mock):
        """Test service call say with http response 400."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        aioclient_mock.get(self.url, params=self.url_param, status=400, content=b"test")

        config = {tts.DOMAIN: {"platform": "google_translate"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "google_translate_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "90% of I person is on front of your door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 0
        assert len(aioclient_mock.mock_calls) == 1

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say_timeout(self, mock_calculate, aioclient_mock):
        """Test service call say with http timeout."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        aioclient_mock.get(self.url, params=self.url_param, exc=asyncio.TimeoutError())

        config = {tts.DOMAIN: {"platform": "google_translate"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "google_translate_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "90% of I person is on front of your door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 0
        assert len(aioclient_mock.mock_calls) == 1

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say_long_size(self, mock_calculate, aioclient_mock):
        """Test service call say with a lot of text."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        self.url_param["total"] = 9
        self.url_param["q"] = "I%20person%20is%20on%20front%20of%20your%20door"
        self.url_param["textlen"] = 33
        for idx in range(9):
            self.url_param["idx"] = idx
            aioclient_mock.get(
                self.url, params=self.url_param, status=200, content=b"test"
            )

        config = {
            tts.DOMAIN: {"platform": "google_translate", "service_name": "google_say"}
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "google_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: (
                    "I person is on front of your door."
                    "I person is on front of your door."
                    "I person is on front of your door."
                    "I person is on front of your door."
                    "I person is on front of your door."
                    "I person is on front of your door."
                    "I person is on front of your door."
                    "I person is on front of your door."
                    "I person is on front of your door."
                ),
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert len(aioclient_mock.mock_calls) == 9
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".mp3") != -1
