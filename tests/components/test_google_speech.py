"""The tests for the Google speech component."""
from unittest.mock import patch

from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, MEDIA_TYPE_SPEECH, ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP)
import homeassistant.components.google_speech as google_speech
from homeassistant.bootstrap import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_service)


class TestGoogleSpeech(object):
    """Test the Google speech component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        config = {
            'google_speech': {
                'lang': 'en',
            }
        }

        with assert_setup_component(1):
            setup_component(self.hass, 'google_speech', config)

    @patch('gtts_token.gtts_token.Token.calculate_token', autospec=True,
           return_value=5)
    def test_service_say(self, mock_calculate):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {
            'google_speech': {}
        }

        with assert_setup_component(1):
            setup_component(self.hass, 'google_speech', config)

        google_speech.say(
            self.hass, "I person is on front of your door. Please open.")
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_SPEECH
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID] == \
        """http://translate.google.com/translate_tts?tl=en&"""
        """q=I%20person%20is%20on%20front%20of%20your%20door.%20Please"""
        """%20open.&tk=5&client=hass&textlen=65"""
