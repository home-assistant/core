"""Constants for the Soundavo WS66i 6-Zone Amplifier Media Player component."""

from datetime import timedelta

DOMAIN = "ws66i"

CONF_SOURCES = "sources"

CONF_SOURCE_1 = "source_1"
CONF_SOURCE_2 = "source_2"
CONF_SOURCE_3 = "source_3"
CONF_SOURCE_4 = "source_4"
CONF_SOURCE_5 = "source_5"
CONF_SOURCE_6 = "source_6"

INIT_OPTIONS_DEFAULT = {
    "1": "Source 1",
    "2": "Source 2",
    "3": "Source 3",
    "4": "Source 4",
    "5": "Source 5",
    "6": "Source 6",
}

POLL_INTERVAL = timedelta(seconds=30)

MAX_VOL = 38
