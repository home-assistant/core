"""Constants for VeSync Component."""

from pyvesync.vesyncbulb import feature_dict as bulb_features
from pyvesync.vesyncfan import air_features, humid_features
from pyvesync.vesyncoutlet import outlet_config
from pyvesync.vesyncswitch import feature_dict as switch_features

DOMAIN = "vesync"
VS_DISCOVERY = "vesync_discovery_{}"
SERVICE_UPDATE_DEVS = "update_devices"

UPDATE_INTERVAL = 60
"""
Update interval for DataCoordinator.

The vesync daily quota formula is 3200 + 1500 * device_count.

An interval of 60 seconds amounts 1440 calls/day which
would be below the 4700 daily quota. For 2 devices, the
total would be 2880.

Using 30 seconds interval gives 8640 for 3 devices which
exceeds the quota of 7700.
"""
VS_DEVICES = "devices"
VS_COORDINATOR = "coordinator"
VS_MANAGER = "manager"
VS_NUMBERS = "numbers"

VS_HUMIDIFIER_MODE_AUTO = "auto"
VS_HUMIDIFIER_MODE_HUMIDITY = "humidity"
VS_HUMIDIFIER_MODE_MANUAL = "manual"
VS_HUMIDIFIER_MODE_SLEEP = "sleep"

DEV_TYPE_TO_HA = {}

for device_name, device in bulb_features.items():
    if "dimmable" in device["features"]:
        DEV_TYPE_TO_HA[device_name] = "bulb-dimmable"

    if "color_temp" in device["features"]:
        DEV_TYPE_TO_HA[device_name] = "bulb-tunable-white"

for device_name in air_features:
    DEV_TYPE_TO_HA[device_name] = "fan"

for device_name in humid_features:
    DEV_TYPE_TO_HA[device_name] = "humidifier"

for device_name in outlet_config:
    DEV_TYPE_TO_HA[device_name] = "outlet"

for device_name, device in switch_features.items():
    if "dimmable" in device["features"]:
        DEV_TYPE_TO_HA[device_name] = "walldimmer"
    else:
        DEV_TYPE_TO_HA[device_name] = "switch"

SKU_TO_BASE_DEVICE = {}

for device_name, device_data in (air_features | humid_features).items():
    for sku in device_data["models"]:
        SKU_TO_BASE_DEVICE[sku] = device_name
