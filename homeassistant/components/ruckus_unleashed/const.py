"""Constants for the Ruckus Unleashed integration."""
import logging

DOMAIN = "ruckus_unleashed"
PLATFORMS = ["device_tracker"]
SCAN_INTERVAL = 180

_LOGGER = logging.getLogger(__package__)

COORDINATOR = "coordinator"
UNDO_UPDATE_LISTENERS = "undo_update_listeners"

CLIENTS = "clients"
MESH_INFO = "mesh_info"

RESPONSE_HOST_NAME = "Host Name"
RESPONSE_MAC_ADDRESS = "MAC Address"
