"""Constants for the Ampio integration."""

from typing import Final

from ampio_mqtt import AccessTier

from homeassistant.const import Platform

DOMAIN: Final = "ampio"

PLATFORMS: Final = [Platform.SENSOR]

DEFAULT_HOST: Final = "ampio.local"

ADMIN_USERNAME: Final = AccessTier.ADMIN.value

HUB_IDENTIFIER: Final = (DOMAIN, "hub")
