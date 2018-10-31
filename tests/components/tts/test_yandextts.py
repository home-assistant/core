"""The tests for the Yandex SpeechKit speech platform."""
import asyncio
import os
import shutil

import homeassistant.components.tts as tts
from homeassistant.setup import setup_component
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, DOMAIN as DOMAIN_MP)
from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_service)

from .test_init import mutagen_mock  # noqa


class TestTTSYandexPlatform:
    """Test the speech component."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self._base_url = "https://tts.voicetech.yandex.net/generate?"

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

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'en-US',
            'key': '1234567xx',
            'speaker': 'zahar',
            'format': 'mp3',
            'emotion': 'neutral',
            'speed': 1
        }
        aioclient_mock.get(
            self._base_url, status=200, content=b'test', params=url_param)

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

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'ru-RU',
            'key': '1234567xx',
            'speaker': 'zahar',
            'format': 'mp3',
            'emotion': 'neutral',
            'speed': 1
        }
        aioclient_mock.get(
            self._base_url, status=200, content=b'test', params=url_param)

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

    def test_service_say_russian_service(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'ru-RU',
            'key': '1234567xx',
            'speaker': 'zahar',
            'format': 'mp3',
            'emotion': 'neutral',
            'speed': 1
        }
        aioclient_mock.get(
            self._base_url, status=200, content=b'test', params=url_param)

        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
                'api_key': '1234567xx',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'yandextts_say', {
            tts.ATTR_MESSAGE: "HomeAssistant",
            tts.ATTR_LANGUAGE: "ru-RU"
        })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert len(calls) == 1

    def test_service_say_timeout(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'en-US',
            'key': '1234567xx',
            'speaker': 'zahar',
            'format': 'mp3',
            'emotion': 'neutral',
            'speed': 1
        }
        aioclient_mock.get(
            self._base_url, status=200,
            exc=asyncio.TimeoutError(), params=url_param)

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

        assert len(calls) == 0
        assert len(aioclient_mock.mock_calls) == 1

    def test_service_say_http_error(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'en-US',
            'key': '1234567xx',
            'speaker': 'zahar',
            'format': 'mp3',
            'emotion': 'neutral',
            'speed': 1
        }
        aioclient_mock.get(
            self._base_url, status=403, content=b'test', params=url_param)

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

        assert len(calls) == 0

    def test_service_say_specified_speaker(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'en-US',
            'key': '1234567xx',
            'speaker': 'alyss',
            'format': 'mp3',
            'emotion': 'neutral',
            'speed': 1
        }
        aioclient_mock.get(
            self._base_url, status=200, content=b'test', params=url_param)

        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
                'api_key': '1234567xx',
                'voice': 'alyss'
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

    def test_service_say_specified_emotion(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'en-US',
            'key': '1234567xx',
            'speaker': 'zahar',
            'format': 'mp3',
            'emotion': 'evil',
            'speed': 1
        }
        aioclient_mock.get(
            self._base_url, status=200, content=b'test', params=url_param)

        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
                'api_key': '1234567xx',
                'emotion': 'evil'
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

    def test_service_say_specified_low_speed(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'en-US',
            'key': '1234567xx',
            'speaker': 'zahar',
            'format': 'mp3',
            'emotion': 'neutral',
            'speed': '0.1'
        }
        aioclient_mock.get(
            self._base_url, status=200, content=b'test', params=url_param)

        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
                'api_key': '1234567xx',
                'speed': 0.1
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

    def test_service_say_specified_speed(self, aioclient_mock):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'en-US',
            'key': '1234567xx',
            'speaker': 'zahar',
            'format': 'mp3',
            'emotion': 'neutral',
            'speed': 2
        }
        aioclient_mock.get(
            self._base_url, status=200, content=b'test', params=url_param)

        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
                'api_key': '1234567xx',
                'speed': 2
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

    def test_service_say_specified_options(self, aioclient_mock):
        """Test service call say with options."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        url_param = {
            'text': 'HomeAssistant',
            'lang': 'en-US',
            'key': '1234567xx',
            'speaker': 'zahar',
            'format': 'mp3',
            'emotion': 'evil',
            'speed': 2
        }
        aioclient_mock.get(
            self._base_url, status=200, content=b'test', params=url_param)
        config = {
            tts.DOMAIN: {
                'platform': 'yandextts',
                'api_key': '1234567xx',
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(tts.DOMAIN, 'yandextts_say', {
            tts.ATTR_MESSAGE: "HomeAssistant",
            'options': {
                'emotion': 'evil',
                'speed': 2,
            }
        })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert len(calls) == 1
