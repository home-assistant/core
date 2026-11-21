"""Constants for the Adax integration."""

import datetime as dt
from typing import Final

ACCOUNT_ID: Final = "account_id"
CLOUD = "Cloud"
CONNECTION_TYPE = "connection_type"
DOMAIN: Final = "adax"
LOCAL = "Local"
WIFI_SSID = "wifi_ssid"
WIFI_PSWD = "wifi_pswd"

SCAN_INTERVAL = dt.timedelta(seconds=60)
# How long the cloud coordinator keeps showing its last data while polls get
# nothing new, before it marks the entities unavailable and logs in again.
STALE_DATA_TIMEOUT = dt.timedelta(minutes=10)
# Once the client's 30 s wait has passed, adax 0.4.0 takes at most about 50 s
# to send a command (log in, then send). It can also wait for ever on a failed
# request, so give up after this many seconds.
COMMAND_TIMEOUT = 60
