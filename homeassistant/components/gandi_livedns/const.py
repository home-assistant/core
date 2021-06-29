"""Constants for the gandi_livedns integration."""

DOMAIN = "gandi_livedns"

CONF_IPV6 = "ipv6"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_TIMEOUT = 15  # in seconds
DEFAULT_TTL = 3600
DEFAULT_TYPE = "A"
DEFAULT_IPV6 = False
DEFAULT_UPDATE_INTERVAL = 10  # in minutes

AVAILABLE_TYPE = [
    "A",
    "AAAA",
    "MX",
]

IPV4_PROVIDER_URL = "https://api.ipify.org"
IPV6_PROVIDER_URL = "https://api6.ipify.org"

GANDI_LIVEDNS_API_URL = (
    "https://api.gandi.net/v5/livedns/domains/{domain}/records/{rrname}/{rrtype}"
)

# Services
SERVICE_UPDATE_RECORDS = "update_records"
DATA_UPDATE_INTERVAL = "data_update_interval"
