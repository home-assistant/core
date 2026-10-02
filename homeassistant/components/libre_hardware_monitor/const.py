"""Constants for the LibreHardwareMonitor integration."""

DOMAIN = "libre_hardware_monitor"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8085
DEFAULT_SCAN_INTERVAL = 10
# LHM can report a partial hardware tree while the PC boots or shuts down.
ORPHANED_DEVICE_REMOVAL_POLLS = 6
