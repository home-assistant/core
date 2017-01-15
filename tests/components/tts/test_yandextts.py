"""The tests for the Yandex SpeechKit speech platform."""
import asyncio
import os
import shutil

import homeassistant.components.tts as tts
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, ATTR_MEDIA_CONTENT_ID, DOMAIN as DOMAIN_MP)
from homeassistant.bootstrap import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_service)


class TestTTSYandexPlatform(object):
    """Test the speech component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.base_url="https://tts.voicetech.yandex.net/generate?"

    def teardown_method(self):
        """Stop everything that was started."""
        default_tts = self.hass.config.path(tts.DEFAULT_CACHE_DIR)
        if os.path.isdir(default_tts):
            shutil.rmtree(default_tts)

        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
                'api_key': '1234567xx'
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_setup_component_without_api_key(self):
        """Test setup component without api key."""
        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
            }
        }

        with assert_setup_component(0, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_service_say(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url = "https://tts.voicetech.yandex.net/generate?format=mp3&speaker=zahar&key=1234567xx&text=HomeAssistant&lang=en-US"
        aioclient_mock.get(
            url, status=200, content=b'test')

        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
                'api_key': '1234567xx'
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'yandextts_say', {
            tts.ATTR_MESSAGE: "HomeAssistant",
        })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert len(calls) == 1

    def test_service_say_russian_config(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url = "https://tts.voicetech.yandex.net/generate?format=mp3&speaker=zahar&key=1234567xx&text=HomeAssistant&lang=ru-RU"
        aioclient_mock.get(
            url, status=200, content=b'test')

        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
                'api_key': '1234567xx',
                'language': 'ru-RU',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'yandextts_say', {
            tts.ATTR_MESSAGE: "HomeAssistant",
        })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert len(calls) == 1



