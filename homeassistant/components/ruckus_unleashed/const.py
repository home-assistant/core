"""Constants for the Ruckus Unleashed integration."""
from homeassistant.const import Platform

DOMAIN = "ruckus_unleashed"
PLATFORMS = [Platform.DEVICE_TRACKER]
SCAN_INTERVAL = 30

MANUFACTURER = "Ruckus"

COORDINATOR = "coordinator"
UNDO_UPDATE_LISTENERS = "undo_update_listeners"

KEY_SYS_CLIENTS = "clients"
KEY_SYS_TITLE = "title"
KEY_SYS_SERIAL = "serial"

API_MESH_NAME = "name"
API_MESH_PSK = "psk"

API_CLIENT_HOSTNAME = "hostname"
API_CLIENT_MAC = "mac"
API_CLIENT_IP = "ip"
API_CLIENT_AP_MAC = "ap"

API_AP_MAC = "mac"
API_AP_SERIALNUMBER = "serial"
API_AP_DEVNAME = "devname"
API_AP_MODEL = "model"
API_AP_FIRMWAREVERSION = "version"

API_SYS_SYSINFO = "sysinfo"
API_SYS_SYSINFO_VERSION = "version"
API_SYS_SYSINFO_SERIAL = "serial"
API_SYS_IDENTITY = "identity"
API_SYS_IDENTITY_NAME = "name"
API_SYS_UNLEASHEDNETWORK = "unleashed-network"
API_SYS_UNLEASHEDNETWORK_TOKEN = "unleashed-network-token"
