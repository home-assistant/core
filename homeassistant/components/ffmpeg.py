"""
Component that will help set the ffmpeg component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ffmpeg/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN = 'ffmpeg'
REQUIREMENTS = ["ha-ffmpeg==0.13"]

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
    """Return ffmpeg binary from config."""
    return FFMPEG_CONFIG.get(CONF_FFMPEG_BIN)


def run_test(input_source):
    """Run test on this input. TRUE is deactivate or run correct."""
    from haffmpeg import Test

    if FFMPEG_CONFIG.get(CONF_RUN_TEST):
        # if in cache
        if input_source in FFMPEG_TEST_CACHE:
            return FFMPEG_TEST_CACHE[input_source]

        # run test
        test = Test(get_binary())
        if not test.run_test(input_source):
            _LOGGER.error("FFmpeg '%s' test fails!", input_source)
            FFMPEG_TEST_CACHE[input_source] = False
            return False
        FFMPEG_TEST_CACHE[input_source] = True
    return True
