"""Constants for the Samsung ExLink integration."""

import logging

from samsung_exlink import SamsungTV

from homeassistant.config_entries import ConfigEntry

LOGGER = logging.getLogger(__package__)
DOMAIN = "samsung_exlink"

type SamsungExLinkConfigEntry = ConfigEntry[SamsungTV]
