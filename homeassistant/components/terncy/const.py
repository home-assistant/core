"""Constants for the Terncy integration."""

DOMAIN = "terncy"
HA_CLIENT_ID = "homeass_nbhQ43"

TERNCY_HUB_ID_PREFIX = "box-"
TERNCY_HUB_SVC_NAME = "_websocket._tcp.local."
TERNCY_MANU_NAME = "Xiaoyan Tech."

TERNCY_EVENT_SVC_ADD = "terncy_svc_add"
TERNCY_EVENT_SVC_REMOVE = "terncy_svc_remove"
TERNCY_EVENT_SVC_UPDATE = "terncy_svc_update"

PROFILE_COLOR_DIMMABLE_LIGHT = 26
PROFILE_COLOR_LIGHT = 8
PROFILE_COLOR_TEMPERATURE_LIGHT = 13
PROFILE_DIMMABLE_COLOR_TEMPERATURE_LIGHT = 17
PROFILE_DIMMABLE_LIGHT = 19
PROFILE_DIMMABLE_LIGHT2 = 20
PROFILE_EXTENDED_COLOR_LIGHT = 12
PROFILE_EXTENDED_COLOR_LIGHT2 = 27
PROFILE_ONOFF_LIGHT = 2

CONF_DEVID = "dev_id"
CONF_DEVICE = "device"
CONF_NAME = "dn"
CONF_HOST = "host"
CONF_IP = "ip"
CONF_PORT = "port"


class TerncyHassPlatformData:
    """Hold HASS platform data for Terncy component."""

    def __init__(self):
        """Create platform data."""
        self.mac = ""
        self.hass = None
        self.hub_entry = None
        self.initialized = False
        self.parsed_devices = {}
