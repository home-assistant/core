"""
Component that will help set the ffmpeg component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ffmpeg/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN = 'ffmpeg'
REQUIREMENTS = ["ha-ffmpeg==1.0"]

_LOGGER = logging.getLogger(__name__)

DATA_FFMPEG = 'ffmpeg'

CONF_INPUT = 'input'
CONF_FFMPEG_BIN = 'ffmpeg_bin'
CONF_EXTRA_ARGUMENTS = 'extra_arguments'
CONF_OUTPUT = 'output'
CONF_RUN_TEST = 'run_test'

DEFAULT_BINARY = 'ffmpeg'
DEFAULT_RUN_TEST = True

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_FFMPEG_BIN, default=DEFAULT_BINARY): cv.string,
        vol.Optional(CONF_RUN_TEST, default=DEFAULT_RUN_TEST): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the FFmpeg component."""
    conf = config.get(DOMAIN, {})

    hass.data[DATA_FFMPEG] = FFmpegManager(
        hass,
        conf.get(CONF_FFMPEG_BIN, DEFAULT_BINARY),
        conf.get(CONF_RUN_TEST, DEFAULT_RUN_TEST)
    )

    return True


class FFmpegManager(object):
    """Helper for ha-ffmpeg."""

    def __init__(self, hass, ffmpeg_bin, run_test):
        """Initialize helper."""
        self.hass = hass
        self._cache = {}
        self._bin = ffmpeg_bin
        self._run_test = run_test

    @property
    def binary(self):
        """Return ffmpeg binary from config."""
        return self._bin

    @asyncio.coroutine
    def async_run_test(self, input_source):
        """Run test on this input. TRUE is deactivate or run correct.

        This method must be run in the event loop.
        """
        from haffmpeg import Test

        if self._run_test:
            # if in cache
            if input_source in self._cache:
                return self._cache[input_source]

            # run test
            ffmpeg_test = Test(self.binary, loop=hass.loop)
            success = yield from ffmpeg_test.run_test(input_source)
            if not success:
                _LOGGER.error("FFmpeg '%s' test fails!", input_source)
                self._cache[input_source] = False
                return False
            self._cache[input_source] = True
        return True
