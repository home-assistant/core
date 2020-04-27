"""Constants for the Livebox component."""
DOMAIN = "livebox"
COORDINATOR = "coordinator"
UNSUB_LISTENER = "unsubscribe_listener"
LIVEBOX_ID = "id"
LIVEBOX_API = "api"
COMPONENTS = ["sensor", "binary_sensor", "device_tracker", "switch"]

TEMPLATE_SENSOR = "Orange Livebox"

DEFAULT_USERNAME = "admin"
DEFAULT_HOST = "192.168.1.1"
DEFAULT_PORT = 80

CONF_LAN_TRACKING = "lan_tracking"
DEFAULT_LAN_TRACKING = False

ATTR_SENSORS = {
    "down": {
        "name": "Orange Livebox Download speed",
        "current_rate": "DownstreamCurrRate",
        "attr": {
            "downstream_maxrate": "DownstreamMaxRate",
            "downstream_lineattenuation": "DownstreamLineAttenuation",
            "downstream_noisemargin": "DownstreamNoiseMargin",
            "downstream_power": "DownstreamPower",
        },
    },
    "up": {
        "name": "Orange Livebox Upload speed",
        "current_rate": "UpstreamCurrRate",
        "attr": {
            "upstream_maxrate": "UpstreamMaxRate",
            "upstream_lineattenuation": "UpstreamLineAttenuation",
            "upstream_noisemargin": "UpstreamNoiseMargin",
            "upstream_power": "UpstreamPower",
        },
    },
}
