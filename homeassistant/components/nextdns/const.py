"""Constants for NextDNS integration."""

from datetime import timedelta

ATTR_CONNECTION = "connection"
ATTR_DNSSEC = "dnssec"
ATTR_ENCRYPTION = "encryption"
ATTR_IP_VERSIONS = "ip_versions"
ATTR_PROTOCOLS = "protocols"
ATTR_SETTINGS = "settings"
ATTR_STATUS = "status"

CONF_PROFILE_ID = "profile_id"

UPDATE_INTERVAL_CONNECTION = timedelta(minutes=5)
UPDATE_INTERVAL_ANALYTICS = timedelta(minutes=10)
UPDATE_INTERVAL_SETTINGS = timedelta(minutes=1)

DOMAIN = "nextdns"
