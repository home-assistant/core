"""Constants for the elmax-cloud integration."""

from homeassistant.const import Platform

DOMAIN = "elmax"
CONF_ELMAX_USERNAME = "username"
CONF_ELMAX_PASSWORD = "password"
CONF_ELMAX_PANEL_ID = "panel_id"
CONF_ELMAX_PANEL_LOCAL_ID = "panel_local_id"
CONF_ELMAX_PANEL_REMOTE_ID = "panel_remote_id"
CONF_ELMAX_PANEL_PIN = "panel_pin"
CONF_ELMAX_PANEL_NAME = "panel_name"

CONF_ELMAX_MODE = "mode"
CONF_ELMAX_MODE_CLOUD = "cloud"
CONF_ELMAX_MODE_DIRECT = "direct"
CONF_ELMAX_MODE_DIRECT_HOST = "panel_api_host"
CONF_ELMAX_MODE_DIRECT_PORT = "panel_api_port"
CONF_ELMAX_MODE_DIRECT_SSL = "use_ssl"
CONF_ELMAX_MODE_DIRECT_SSL_CERT = "ssl_cert"

ELMAX_LOCAL_API_PATH = "api/v2"

CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_ENDPOINT_ID = "endpoint_id"

ELMAX_PLATFORMS = [
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.ALARM_CONTROL_PANEL,
    Platform.COVER,
]

ELMAX_MODE_DIRECT_DEFAULT_HTTPS_PORT = 443
ELMAX_MODE_DIRECT_DEFAULT_HTTP_PORT = 80
POLLING_SECONDS = 30
DEFAULT_TIMEOUT = 10.0
MIN_APIV2_SUPPORTED_VERSION = "4.9.13"
