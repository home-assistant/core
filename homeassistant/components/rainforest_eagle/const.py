"""Constants for the Rainforest Eagle integration."""
from datetime import timedelta

DOMAIN = "rainforest_eagle"

CONF_CLOUD_ID = "cloud_id"
CONF_INSTALL_CODE = "install_code"
POWER_KILO_WATT = "kW"

MIN_SCAN_INTERVAL = timedelta(seconds=30)

# Backwards compatibility for yaml config
# CONFIG_SCHEMA = vol.Schema(
#    {
#        DOMAIN: vol.Schema(
#            {
#                vol.Required(CONF_IP_ADDRESS): str,
#                vol.Required(CONF_CLOUD_ID): str,
#                vol.Required(CONF_INSTALL_CODE): str,
#            }
#        )
#    }
# )
#
