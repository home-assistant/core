"""Constants for the Ruckus Unleashed integration."""
from homeassistant.const import Platform

DOMAIN = "ruckus_unleashed"
PLATFORMS = [Platform.DEVICE_TRACKER]
SCAN_INTERVAL = 180

MANUFACTURER = "Ruckus"

COORDINATOR = "coordinator"
UNDO_UPDATE_LISTENERS = "undo_update_listeners"

API_CLIENTS = "clients"
API_NAME = "host_name"
API_MAC = "mac_address"
API_IP = "user_ip"
API_SYSTEM_OVERVIEW = "system_overview"
API_SERIAL = "serial_number"
API_DEVICE_NAME = "device_name"
API_MODEL = "model"
API_VERSION = "version"
API_AP = "ap"
API_ID = "id"
API_CURRENT_ACTIVE_CLIENTS = "current_active_clients"
API_ACCESS_POINT = "access_point"
