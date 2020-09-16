"""Constants for the Govee LED strips integration."""

import voluptuous as vol
from homeassistant.const import CONF_API_KEY, CONF_DELAY

DOMAIN = "govee"

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_API_KEY): str, vol.Optional(CONF_DELAY, default=10): int}
)
