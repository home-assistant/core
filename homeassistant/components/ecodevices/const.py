"""Constant for the eco-devices integration."""
DOMAIN = "ecodevices"

CONTROLLER = "controller"
COORDINATOR = "coordinator"
PLATFORMS = ["sensor"]
UNDO_UPDATE_LISTENER = "undo_update_listener"

CONF_T1_ENABLED = "t1_enabled"
CONF_T1_HCHP = "t1_hchp"
CONF_T2_ENABLED = "t2_enabled"
CONF_T2_HCHP = "t2_hchp"
CONF_C1_ENABLED = "c1_enabled"
CONF_C1_UNIT_OF_MEASUREMENT = "c1_unit_of_measurement"
CONF_C1_TOTAL_UNIT_OF_MEASUREMENT = "c1_total_unit_of_measurement"
CONF_C1_DEVICE_CLASS = "c1_device_class"
CONF_C2_ENABLED = "c2_enabled"
CONF_C2_UNIT_OF_MEASUREMENT = "c2_unit_of_measurement"
CONF_C2_TOTAL_UNIT_OF_MEASUREMENT = "c2_total_unit_of_measurement"
CONF_C2_DEVICE_CLASS = "c2_device_class"

DEFAULT_T1_NAME = "Teleinfo 1"
DEFAULT_T2_NAME = "Teleinfo 2"
DEFAULT_C1_NAME = "Meter 1"
DEFAULT_C2_NAME = "Meter 2"
DEFAULT_SCAN_INTERVAL = 5
