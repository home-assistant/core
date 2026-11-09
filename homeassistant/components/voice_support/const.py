"""Constants for Voice support."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "voice_support"

PREVIEW_FEATURE_WAKE_WORD_VERIFICATION = "wake_word_verification"

APP_NAME = "Voice"

# The prefix depends on REPOSITORY_URL
APP_SLUG = "542a9043_voice"

REPOSITORY_URL = "https://github.com/OHF-Voice/apps"

DEFAULT_PORT = 10800

API_VERSION = 1

# Timeouts in seconds
DISCOVERY_TIMEOUT = 120
INFO_TIMEOUT = 10
RUN_TIMEOUT = 10

INFO_INTERVAL_MINUTES = 10
