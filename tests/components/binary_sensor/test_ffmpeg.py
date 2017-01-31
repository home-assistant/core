"""The tests for Home Assistant ffmpeg binary sensor."""
from unittest.mock import patch

from homeassistant.bootstrap import setup_component
from homeassistant.util.async import run_callback_threadsafe

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_coro)


class TestFFmpegNoiseSetup(object):
    """Test class for ffmpeg."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {
            'ffmpeg': {
                'run_test': False,
            },
            'binary_sensor': {
                'platform': 'ffmpeg_noise',
                'input': 'testinputvideo',
            },
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Setup ffmpeg component."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config)

        assert self.hass.data['ffmpeg'].binary == 'ffmpeg'
        assert len(self.hass.data['ffmpeg'].entities) == 1

    @patch('haffmpeg.SensorNoise.open_sensor', return_value=mock_coro()())
    def test_setup_component_start(self, mock_start):
        """Setup ffmpeg component."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config)

        assert self.hass.data['ffmpeg'].binary == 'ffmpeg'
        assert len(self.hass.data['ffmpeg'].entities) == 1

        entity = self.hass.data['ffmpeg'].entities[0]
        self.hass.start()
        assert mock_start.called

        assert entity.state == 'off'
        run_callback_threadsafe(
            self.hass.loop, entity._async_callback, True).result()
        assert entity.state == 'on'


class TestFFmpegMotionSetup(object):
    """Test class for ffmpeg."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {
            'ffmpeg': {
                'run_test': False,
            },
            'binary_sensor': {
                'platform': 'ffmpeg_motion',
                'input': 'testinputvideo',
            },
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Setup ffmpeg component."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config)

        assert self.hass.data['ffmpeg'].binary == 'ffmpeg'
        assert len(self.hass.data['ffmpeg'].entities) == 1

    @patch('haffmpeg.SensorMotion.open_sensor', return_value=mock_coro()())
    def test_setup_component_start(self, mock_start):
        """Setup ffmpeg component."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config)

        assert self.hass.data['ffmpeg'].binary == 'ffmpeg'
        assert len(self.hass.data['ffmpeg'].entities) == 1

        entity = self.hass.data['ffmpeg'].entities[0]
        self.hass.start()
        assert mock_start.called

        assert entity.state == 'off'
        run_callback_threadsafe(
            self.hass.loop, entity._async_callback, True).result()
        assert entity.state == 'on'
