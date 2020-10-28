"""The tests for the Microsoft speech platform."""
import asyncio
import os
import shutil

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
import homeassistant.components.tts as tts
from homeassistant.config import async_process_ha_core_config
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant, mock_service


class TestTTSMicrosoftSpeechPlatform:
    """Test the Microsoft speech component."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        asyncio.run_coroutine_threadsafe(
            async_process_ha_core_config(
                self.hass, {"internal_url": "http://example.local:8123"}
            ),
            self.hass.loop,
        )

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
                "platform": "microsoft_speech",
                "api_key": "123456789abcdefghijklmnopqrstuvwxyz",
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_setup_component_all_params(self):
        """Test setup component with all parameters."""
        config = {
            tts.DOMAIN: {
                "platform": "microsoft_speech",
                "api_key": "123456789abcdefghijklmnopqrstuvwxyz",
                "region": "westeurope",
                "language": "nl-NL",
                "type": "ColetteNeural",
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say(self, mock_calculate):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {
            tts.DOMAIN: {
                "platform": "microsoft_speech",
                "api_key": "123456789abcdefghijklmnopqrstuvwxyz",
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

            self.hass.services.call(
                tts.DOMAIN,
                "microsoft_speech_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
            self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".wav") != -1

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say_error_region(self, mock_calculate):
        """Test service call say error on region."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {
            tts.DOMAIN: {
                "platform": "microsoft_speech",
                "api_key": "123456789abcdefghijklmnopqrstuvwxyz",
                "region": "nonexistingregion",
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

            self.hass.services.call(
                tts.DOMAIN,
                "microsoft_speech_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
            self.hass.block_till_done()

        assert len(calls) == 0

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say_error_language(self, mock_calculate):
        """Test service call say error on language."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {
            tts.DOMAIN: {
                "platform": "microsoft_speech",
                "api_key": "123456789abcdefghijklmnopqrstuvwxyz",
                "language": "nonexistinglanguage",
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

            self.hass.services.call(
                tts.DOMAIN,
                "microsoft_speech_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
            self.hass.block_till_done()

        assert len(calls) == 0

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say_error_type(self, mock_calculate):
        """Test service call say error on type."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {
            tts.DOMAIN: {
                "platform": "microsoft_speech",
                "api_key": "123456789abcdefghijklmnopqrstuvwxyz",
                "type": "nonexistingtype",
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

            self.hass.services.call(
                tts.DOMAIN,
                "microsoft_speech_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
            self.hass.block_till_done()

        assert len(calls) == 0

    @patch("gtts_token.gtts_token.Token.calculate_token", autospec=True, return_value=5)
    def test_service_say_dutch(self, mock_calculate):
        """Test service call say in Dutch."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {
            tts.DOMAIN: {
                "platform": "microsoft_speech",
                "api_key": "123456789abcdefghijklmnopqrstuvwxyz",
                "region": "westeurope",
                "language": "nl-NL",
                "type": "ColetteNeural",
            }
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

            self.hass.services.call(
                tts.DOMAIN,
                "microsoft_speech_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "Voordat ik een fout maak, maak ik die fout niet.",
                },
            )
            self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".wav") != -1
