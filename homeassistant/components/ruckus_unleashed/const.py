"""Constants for the Ruckus integration."""

from homeassistant.const import Platform

DOMAIN = "ruckus_unleashed"
PLATFORMS = [Platform.DEVICE_TRACKER]
SCAN_INTERVAL = 30

CONF_MAC_FILTER = "mac_filter"

MANUFACTURER = "Ruckus"

KEY_SYS_CLIENTS = "clients"
KEY_SYS_TITLE = "title"
KEY_SYS_SERIAL = "serial"

API_MESH_NAME = "name"

API_CLIENT_HOSTNAME = "hostname"
API_CLIENT_MAC = "mac"
API_CLIENT_IP = "ip"

API_AP_MAC = "mac"
API_AP_DEVNAME = "devname"
API_AP_MODEL = "model"
API_AP_FIRMWAREVERSION = "version"

API_SYS_SYSINFO = "sysinfo"
API_SYS_SYSINFO_VERSION = "version"
API_SYS_SYSINFO_SERIAL = "serial"
