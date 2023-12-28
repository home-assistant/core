"""Constants for the E3DC Hauskraftwerk integration."""

DOMAIN = "e3dc_modbus"
DEFAULT_NAME = "E3DC Hauskraftwerk"
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_PORT = 502
DEFAULT_MODBUS_ADDRESS = 1
CONF_E3DC_HUB = "e3dc_hub"
ATTR_STATUS_DESCRIPTION = "status_description"
ATTR_MANUFACTURER = "E3DC"
CONF_MODBUS_ADDRESS = "modbus_address"
CONF_WALLBOX_IPADRESS = ""


DEVICE_STATUSSES = {
    1: "Off",
    2: "Sleeping (auto-shutdown) – Night mode",
    3: "Grid Monitoring/wake-up",
    4: "Inverter is ON and producing power",
    5: "Production (curtailed)",
    6: "Shutting down",
    7: "Fault",
    8: "Maintenance/setup",
}
