"""Constants for the Bluetooth LE Tracker integration."""

DOMAIN = "bluetooth_le_tracker"
CONF_TRACK_BATTERY = "track_battery"
CONF_TRACK_BATTERY_INTERVAL = "track_battery_interval"

DEFAULT_TRACK_BATTERY = False
DEFAULT_TRACK_BATTERY_INTERVAL = 86400
SIGNAL_BLE_DEVICE_NEW = "bluetooth_le_tracker_new_device"
SIGNAL_BLE_DEVICE_UNAVAILABLE = "bluetooth_le_tracker_unavailable_device"
SIGNAL_BLE_DEVICE_SEEN = "bluetooth_le_tracker_seen_device"
SIGNAL_BLE_DEVICE_BATTERY_UPDATE = "bluetooth_le_tracker_battery_update"

ATTR_ADDRESS = "address"
ATTR_RSSI = "rssi"

BLE_PREFIX = "BLE_"
