"""Constants for the Discord integration."""

from typing import Final

from homeassistant.const import CONF_URL

DEFAULT_NAME = "Discord"
DOMAIN: Final = "discord"

URL_PLACEHOLDER = {CONF_URL: "https://www.home-assistant.io/integrations/discord"}

DATA_HASS_CONFIG = "discord_hass_config"
