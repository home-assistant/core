"""Constants for Voice support."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "voice_support"

PREVIEW_FEATURE_WAKE_WORD_VERIFICATION = "wake_word_verification"
"""The Labs toggle that decides whether the app hears anything at all.

A satellite asked for its wake word audio detects at a lower threshold, so
an app that is not consulted has to mean a satellite never asked.
"""

APP_NAME = "Voice"

APP_SLUG = "542a9043_voice"
"""The app's slug in the Supervisor's store.

The prefix is the first eight characters of the SHA-1 of the repository
URL, so this is the app as installed from REPOSITORY_URL. One from a fork
has a different slug and is not installed or updated from here, though it is
still discovered and used like any other.
"""

REPOSITORY_URL = "https://github.com/OHF-Voice/apps"
"""Where the app comes from, named when it cannot be found in the store."""

DEFAULT_PORT = 10800
"""What the app listens on, offered when its address is typed in by hand."""

DISCOVERY_TIMEOUT = 120
"""Seconds to wait after starting the app for it to announce itself.

A fresh install builds a decoding graph per wake word before it answers,
which is a minute or so on slow hardware.
"""

API_VERSION = 1
"""The protocol version this speaks. An app answering with a different one
is left alone rather than talked to with the wrong messages."""

INFO_TIMEOUT = 10
"""Seconds to wait for the app to describe itself."""

INFO_INTERVAL_MINUTES = 10
"""How often the app is asked what it can verify now: an update can change
its models without changing where it lives."""

RUN_TIMEOUT = 10
"""Seconds to wait for the app to take a run before getting on without it."""
