"""Constants for the victron_gx integration."""

DOMAIN = "victron_gx"

CONF_INSTALLATION_ID = "installation_id"
CONF_MODEL = "model"
CONF_SERIAL = "serial"

# Not using GenericOnOff as some switches use different enums.
# It has to be with id "on" to be on and "off" to be off.
SWITCH_ON_ID = "on"
SWITCH_OFF_ID = "off"
