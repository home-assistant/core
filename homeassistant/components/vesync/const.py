"""Constants for VeSync Component."""

DOMAIN = "vesync"
VS_DISCOVERY = "vesync_discovery_{}"
SERVICE_UPDATE_DEVS = "update_devices"

VS_SWITCHES = "switches"
VS_FANS = "fans"
VS_LIGHTS = "lights"
VS_SENSORS = "sensors"
VS_MANAGER = "manager"

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
    "ESD16": "walldimmer",
    "ESWD16": "walldimmer",
    "ESL100": "bulb-dimmable",
    "ESL100CW": "bulb-tunable-white",
}

SKU_TO_BASE_DEVICE = {
    # Air Purifiers
    "LV-PUR131S": "LV-PUR131S",
    "LV-RH131S": "LV-PUR131S",  # Alt ID Model LV-PUR131S
    "Core200S": "Core200S",
    "LAP-C201S-AUSR": "Core200S",  # Alt ID Model Core200S
    "LAP-C202S-WUSR": "Core200S",  # Alt ID Model Core200S
    "Core300S": "Core300S",
    "LAP-C301S-WJP": "Core300S",  # Alt ID Model Core300S
    "LAP-C301S-WAAA": "Core300S",  # Alt ID Model Core300S
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
    "Vital100S": "Vital100S",
    "LAP-V102S-WUS": "Vital100S",  # Alt ID Model Vital100S
    "LAP-V102S-AASR": "Vital100S",  # Alt ID Model Vital100S
    "LAP-V102S-WEU": "Vital100S",  # Alt ID Model Vital100S
    "LAP-V102S-WUK": "Vital100S",  # Alt ID Model Vital100S
    "EverestAir": "EverestAir",
    "LAP-EL551S-AUS": "EverestAir",  # Alt ID Model EverestAir
    "LAP-EL551S-AEUR": "EverestAir",  # Alt ID Model EverestAir
    "LAP-EL551S-WEU": "EverestAir",  # Alt ID Model EverestAir
    "LAP-EL551S-WUS": "EverestAir",  # Alt ID Model EverestAir
}
