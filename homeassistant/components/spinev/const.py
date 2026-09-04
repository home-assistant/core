"""Constants for the Spin EV Charger integration."""

from datetime import timedelta
from enum import StrEnum
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "spinev"

MANUFACTURER: Final = "Exicom"
MODEL: Final = "Spin"

PLATFORMS: Final = [Platform.SENSOR]

CONF_CONNECTION_MODE: Final = "connection_mode"
CONF_SERIAL: Final = "serial"


class ConnectionMode(StrEnum):
    """What the integration does with the charger's one Bluetooth slot."""

    PER_POLL = "per_poll"
    """Give the slot back between polls, so the phone app can still reach it."""

    PERSISTENT = "persistent"
    """Hold the slot, which locks every other client out, phone app included."""


DEFAULT_CONNECTION_MODE: Final = ConnectionMode.PER_POLL

#: Poll interval while a vehicle is charging, so power stays current.
CHARGING_INTERVAL: Final = timedelta(seconds=60)
#: Poll interval while idle. Kept long so the charger's single Bluetooth slot
#: is left free for the phone app for long stretches.
IDLE_INTERVAL: Final = timedelta(seconds=300)
