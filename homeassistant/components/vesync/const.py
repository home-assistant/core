"""Constants for VeSync Component."""

from pyvesync.vesyncfan import VeSyncHumid200300S, VeSyncSuperior6000S

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

FAN_NIGHT_LIGHT_LEVEL_DIM = "dim"
FAN_NIGHT_LIGHT_LEVEL_OFF = "off"
FAN_NIGHT_LIGHT_LEVEL_ON = "on"

HUMIDIFIER_NIGHT_LIGHT_LEVEL_BRIGHT = "bright"
HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM = "dim"
HUMIDIFIER_NIGHT_LIGHT_LEVEL_OFF = "off"

VeSyncHumidifierDevice = VeSyncHumid200300S | VeSyncSuperior6000S
"""Humidifier device types"""

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

SKU_TO_BASE_DEVICE = {
    # Air Purifiers
    "LV-PUR131S": "LV-PUR131S",
    "LV-RH131S": "LV-PUR131S",  # Alt ID Model LV-PUR131S
    "LV-RH131S-WM": "LV-PUR131S",  # Alt ID Model LV-PUR131S
    "Core200S": "Core200S",
    "LAP-C201S-AUSR": "Core200S",  # Alt ID Model Core200S
    "LAP-C202S-WUSR": "Core200S",  # Alt ID Model Core200S
    "Core300S": "Core300S",
    "LAP-C301S-WJP": "Core300S",  # Alt ID Model Core300S
    "LAP-C301S-WAAA": "Core300S",  # Alt ID Model Core300S
    "LAP-C302S-WUSB": "Core300S",  # Alt ID Model Core300S
    "Core400S": "Core400S",
    "LAP-C401S-WJP": "Core400S",  # Alt ID Model Core400S
    "LAP-C401S-WUSR": "Core400S",  # Alt ID Model Core400S
    "LAP-C401S-WAAA": "Core400S",  # Alt ID Model Core400S
    "Core600S": "Core600S",
    "LAP-C601S-WUS": "Core600S",  # Alt ID Model Core600S
    "LAP-C601S-WUSR": "Core600S",  # Alt ID Model Core600S
    "LAP-C601S-WEU": "Core600S",  # Alt ID Model Core600S,
    "Vital200S": "Vital200S",
    "LAP-V201S-AASR": "Vital200S",  # Alt ID Model Vital200S
    "LAP-V201S-WJP": "Vital200S",  # Alt ID Model Vital200S
    "LAP-V201S-WEU": "Vital200S",  # Alt ID Model Vital200S
    "LAP-V201S-WUS": "Vital200S",  # Alt ID Model Vital200S
    "LAP-V201-AUSR": "Vital200S",  # Alt ID Model Vital200S
    "LAP-V201S-AEUR": "Vital200S",  # Alt ID Model Vital200S
    "LAP-V201S-AUSR": "Vital200S",  # Alt ID Model Vital200S
    "Vital100S": "Vital100S",
    "LAP-V102S-WUS": "Vital100S",  # Alt ID Model Vital100S
    "LAP-V102S-AASR": "Vital100S",  # Alt ID Model Vital100S
    "LAP-V102S-WEU": "Vital100S",  # Alt ID Model Vital100S
    "LAP-V102S-WUK": "Vital100S",  # Alt ID Model Vital100S
    "LAP-V102S-AUSR": "Vital100S",  # Alt ID Model Vital100S
    "EverestAir": "EverestAir",
    "LAP-EL551S-AUS": "EverestAir",  # Alt ID Model EverestAir
    "LAP-EL551S-AEUR": "EverestAir",  # Alt ID Model EverestAir
    "LAP-EL551S-WEU": "EverestAir",  # Alt ID Model EverestAir
    "LAP-EL551S-WUS": "EverestAir",  # Alt ID Model EverestAir
    "SmartTowerFan": "SmartTowerFan",
    "LTF-F422S-KEU": "SmartTowerFan",  # Alt ID Model SmartTowerFan
    "LTF-F422S-WUSR": "SmartTowerFan",  # Alt ID Model SmartTowerFan
    "LTF-F422_WJP": "SmartTowerFan",  # Alt ID Model SmartTowerFan
    "LTF-F422S-WUS": "SmartTowerFan",  # Alt ID Model SmartTowerFan
}
