"""Constants for the Rituals Perfume Genie integration."""

from datetime import timedelta

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

DOMAIN = "rituals_perfume_genie"

# Alt (API V1)
ACCOUNT_HASH = "account_hash"

# Neu (API V2):
# HA-Standards
USERNAME = CONF_USERNAME
PASSWORD = CONF_PASSWORD

# The API provided by Rituals is currently rate limited to 30 requests
# per hour per IP address. To avoid hitting this limit, the polling
# interval is set to 3 minutes. This also gives a little room for
# Home Assistant restarts.
UPDATE_INTERVAL = timedelta(minutes=3)
