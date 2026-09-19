"""Constants used by the TrueNAS integration."""

from homeassistant.const import Platform

PLATFORMS = [
    Platform.SENSOR,
]

DOMAIN = "truenas_ce"
DEFAULT_NAME = "root"
ATTRIBUTION = "Data provided by TrueNAS CE integration"

# Namespaced: dispatcher signals share a single hass-wide namespace.
SIGNAL_UPDATE_SENSORS = f"{DOMAIN}_update_sensors"

# TrueNAS interface link states (from interface.query -> state/link_state).
LINK_STATE_UP = "LINK_STATE_UP"
LINK_STATE_DOWN = "LINK_STATE_DOWN"

DEFAULT_HOST = "truenas.local"

# kbit/s to KiB/s: 1000 / 8192
KILOBITS_TO_KIBIBYTES_FACTOR = 0.12207

UPTIME_EPOCH_TOLERANCE_SECONDS = 300

QUERY_TIMEOUT: float = 30.0

ERR_CERT_VERIFY_FAILED = "certificate_verify_failed"
ERR_HTTP_USED = "http_used"
ERR_TLS_NOT_SUPPORTED = "tlsv1_not_supported"
ERR_WS_NOT_SUPPORTED = "websocket_not_supported"
ERR_UNKNOWN_HOSTNAME = "unknown_hostname"
ERR_CONNECTION_REFUSED = "connection_refused"
ERR_INVALID_HOSTNAME = "invalid_hostname"
ERR_HANDSHAKE_TIMEOUT = "handshake_timeout"
ERR_INVALID_KEY = "invalid_key"
ERR_PROXY_INTERCEPTED = "proxy_intercepted"
ERR_API_NOT_FOUND = "api_not_found"
ERR_TIMEOUT = "timeout"
ERR_MALFORMED_RESULT = "malformed_result"
ERR_LOST_LOGIN = "connection_lost_mid_login"
ERR_LOST_QUERY = "connection_lost_mid_query"
ERR_UNKNOWN = "unknown_error"

# need for ha ip dns validation, to avoid false positives
KNOWN_DOMAINS = [
    "fritz.box",
    "local",
    "lan",
    "home",
    "speedport.ip",
    "tplinkwifi.net",
    "home.arpa",
    "mshome.net",
    "internal",
]

DEFAULT_DEVICE_NAME = "TrueNAS"
DEFAULT_SSL_VERIFY = False
DEFAULT_DATA_UNIT = "GiB"
ALLOWED_DATA_UNITS = ["GB", "GiB"]

TO_REDACT = {
    "password",
    "passphrase",
    "encryption_password",
    "encryption_salt",
    "host",
    "api_key",
    "serial",
    "system_serial",
    "ip4_addr",
    "ip6_addr",
    "account",
    "key",
    "certificate",
    "privatekey",
    "dataset_passphrases",
}

CONF_DATA_UNIT = "data_unit"

# system.global.id UUID; identifies a device stably across IP changes.
CONF_SYSTEM_ID = "system_id"

DEFAULT_POLL_INTERVAL = 60

CONF_BEHAVIORS = "behaviors"
BEHAVIOR_REMOVE_INACTIVE_NIC = "remove_inactive_nic"
DEFAULT_BEHAVIORS: list[str] = []

ERROR_API_FORMAT = "TrueNAS %s API error calling %s: %s"
