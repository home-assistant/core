"""Constants for the Samsung TV integration."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "samsungtv"

ATTR_PROPERTIES = "properties"

DEFAULT_MANUFACTURER = "Samsung"

VALUE_CONF_NAME = "HomeAssistant"
VALUE_CONF_ID = "ha.component.samsung"

CONF_MANUFACTURER = "manufacturer"
CONF_SSDP_RENDERING_CONTROL_LOCATION = "ssdp_rendering_control_location"
CONF_SSDP_MAIN_TV_AGENT_LOCATION = "ssdp_main_tv_agent_location"
CONF_SESSION_ID = "session_id"

RESULT_AUTH_MISSING = "auth_missing"
RESULT_INVALID_PIN = "invalid_pin"
RESULT_SUCCESS = "success"
RESULT_CANNOT_CONNECT = "cannot_connect"
RESULT_NOT_SUPPORTED = "not_supported"
RESULT_UNKNOWN_HOST = "unknown"

METHOD_LEGACY = "legacy"
METHOD_ENCRYPTED_WEBSOCKET = "encrypted"
METHOD_WEBSOCKET = "websocket"

TIMEOUT_REQUEST = 31
TIMEOUT_WEBSOCKET = 5

LEGACY_PORT = 55000
ENCRYPTED_WEBSOCKET_PORT = 8000
WEBSOCKET_NO_SSL_PORT = 8001
WEBSOCKET_SSL_PORT = 8002
WEBSOCKET_PORTS = (WEBSOCKET_SSL_PORT, WEBSOCKET_NO_SSL_PORT)

SUCCESSFUL_RESULTS = {RESULT_AUTH_MISSING, RESULT_SUCCESS}

UPNP_SVC_RENDERING_CONTROL = "urn:schemas-upnp-org:service:RenderingControl:1"
UPNP_SVC_MAIN_TV_AGENT = "urn:samsung.com:service:MainTVAgent2:1"

# Time to wait before reloading entry upon device config change
ENTRY_RELOAD_COOLDOWN = 5
