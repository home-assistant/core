"""Constants for Electrolux Group integration."""

from homeassistant.const import __version__ as HA_VERSION

DOMAIN = "electrolux_group"

CONF_REFRESH_TOKEN = "refresh_token"

NEW_APPLIANCE = "electrolux_new_appliance"

ELECTROLUX_INTEGRATION_VERSION = "0.0.1"

USER_AGENT = f"HomeAssistant/{HA_VERSION} ElectroluxGroupIntegration/{ELECTROLUX_INTEGRATION_VERSION}"
