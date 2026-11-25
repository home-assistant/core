"""Constants for Electrolux integration."""

from homeassistant.const import UnitOfTemperature, __version__ as HA_VERSION

DOMAIN = "electrolux"

CONF_REFRESH_TOKEN = "refresh_token"

NEW_APPLIANCE_SIGNAL = "electrolux_new_appliance"

USER_AGENT = f"HomeAssistant/{HA_VERSION}"

ELECTROLUX_TO_HA_TEMPERATURE_UNIT = {
    "CELSIUS": UnitOfTemperature.CELSIUS,
    "FAHRENHEIT": UnitOfTemperature.FAHRENHEIT,
}
