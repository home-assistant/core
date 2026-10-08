"""Constants for the Ampio integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "ampio"

PLATFORMS: Final = [Platform.SENSOR]

DEFAULT_HOST: Final = "ampio.local"

# The reserved login of the administrator account.
ADMIN_USERNAME: Final = "admin"
