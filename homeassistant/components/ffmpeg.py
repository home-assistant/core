"""
Component that will help set the ffmpeg component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ffmpeg/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.util.async import run_coroutine_threadsafe

DOMAIN = 'ffmpeg'
REQUIREMENTS = ["ha-ffmpeg==0.14"]

_LOGGER = logging.getLogger(__name__)

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


FFMPEG_CONFIG = {
    CONF_FFMPEG_BIN: DEFAULT_BINARY,
    CONF_RUN_TEST: DEFAULT_RUN_TEST,
}
FFMPEG_TEST_CACHE = {}


def setup(hass, config):
    """Setup the FFmpeg component."""
    if DOMAIN in config:
        FFMPEG_CONFIG.update(config.get(DOMAIN))
    return True


def get_binary():
    """Return ffmpeg binary from config.

    Async friendly.
    """
    return FFMPEG_CONFIG.get(CONF_FFMPEG_BIN)


def run_test(hass, input_source):
    """Run test on this input. TRUE is deactivate or run correct."""
    return run_coroutine_threadsafe(
        async_run_test(hass, input_source), hass.loop).result()


@asyncio.coroutine
def async_run_test(hass, input_source):
    """Run test on this input. TRUE is deactivate or run correct.

    This method must be run in the event loop.
    """
    from haffmpeg import TestAsync

    if FFMPEG_CONFIG.get(CONF_RUN_TEST):
        # if in cache
        if input_source in FFMPEG_TEST_CACHE:
            return FFMPEG_TEST_CACHE[input_source]

        # run test
        ffmpeg_test = TestAsync(get_binary(), loop=hass.loop)
        success = yield from ffmpeg_test.run_test(input_source)
        if not success:
            _LOGGER.error("FFmpeg '%s' test fails!", input_source)
            FFMPEG_TEST_CACHE[input_source] = False
            return False
        FFMPEG_TEST_CACHE[input_source] = True
    return True
