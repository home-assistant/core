"""Constants for VeSync Component."""

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
VS_LISTENERS = "listeners"
VS_NUMBERS = "numbers"

VS_HUMIDIFIER_MODE_AUTO = "auto"
VS_HUMIDIFIER_MODE_HUMIDITY = "humidity"
VS_HUMIDIFIER_MODE_MANUAL = "manual"
VS_HUMIDIFIER_MODE_SLEEP = "sleep"

VS_FAN_MODE_AUTO = "auto"
VS_FAN_MODE_SLEEP = "sleep"
VS_FAN_MODE_ADVANCED_SLEEP = "advancedSleep"
VS_FAN_MODE_TURBO = "turbo"
VS_FAN_MODE_PET = "pet"
VS_FAN_MODE_MANUAL = "manual"
VS_FAN_MODE_NORMAL = "normal"

# not a full list as manual is used as speed not present
VS_FAN_MODE_PRESET_LIST_HA = [
    VS_FAN_MODE_AUTO,
    VS_FAN_MODE_SLEEP,
    VS_FAN_MODE_ADVANCED_SLEEP,
    VS_FAN_MODE_TURBO,
    VS_FAN_MODE_PET,
    VS_FAN_MODE_NORMAL,
]
NIGHT_LIGHT_LEVEL_BRIGHT = "bright"
NIGHT_LIGHT_LEVEL_DIM = "dim"
NIGHT_LIGHT_LEVEL_OFF = "off"

FAN_NIGHT_LIGHT_LEVEL_DIM = "dim"
FAN_NIGHT_LIGHT_LEVEL_OFF = "off"
FAN_NIGHT_LIGHT_LEVEL_ON = "on"

HUMIDIFIER_NIGHT_LIGHT_LEVEL_BRIGHT = "bright"
HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM = "dim"
HUMIDIFIER_NIGHT_LIGHT_LEVEL_OFF = "off"

# need to remove this.  light need it still.
DEV_TYPE_TO_HA = {
    "wifi-switch-1.3": "outlet",
    "ESW03-USA": "outlet",
    "ESW01-EU": "outlet",
    "ESW15-USA": "outlet",
    "ESWL01": "switch",
    "ESWL03": "switch",
    "ESO15-TB": "outlet",
    "LV-PUR131S": "fan",
    "Core200S": "fan",
    "Core300S": "fan",
    "Core400S": "fan",
    "Core600S": "fan",
    "EverestAir": "fan",
    "Vital200S": "fan",
    "Vital100S": "fan",
    "SmartTowerFan": "fan",
    "ESD16": "walldimmer",
    "ESWD16": "walldimmer",
    "ESL100": "bulb-dimmable",
    "ESL100CW": "bulb-tunable-white",
}
