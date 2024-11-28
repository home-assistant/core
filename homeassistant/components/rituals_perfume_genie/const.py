"""Constants for the Rituals Perfume Genie integration."""

from datetime import timedelta

DOMAIN = "rituals_perfume_genie"

ACCOUNT_HASH = "account_hash"

# The API provided by Rituals is currently rate limited to 30 requests
# per hour per IP address. To avoid hitting this limit, the polling
# interval is set to 3 minutes. This also gives a little room for
# Home Assistant restarts.
UPDATE_INTERVAL = timedelta(minutes=3)
