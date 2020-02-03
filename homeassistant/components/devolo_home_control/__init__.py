"""The devolo_home_control integration."""
import voluptuous as vol

from homeassistant.components import switch as ha_switch

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["switch"]

SUPPORTED_PLATFORMS = [ha_switch.DOMAIN]
