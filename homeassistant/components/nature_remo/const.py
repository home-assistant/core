"""Constants for the Nature Remo integration."""

from datetime import timedelta

DOMAIN = "nature_remo"

# 2 requests per cycle out of the account-wide 30 req / 5 min budget.
UPDATE_INTERVAL = timedelta(seconds=60)
