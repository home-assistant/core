"""Constants for VeSync Component."""

DOMAIN = "vesync"
VS_DISCOVERY = "vesync_discovery_{}"
SERVICE_UPDATE_DEVS = "update_devices"

VS_SWITCHES = "switches"
VS_FANS = "fans"
VS_LIGHTS = "lights"
VS_SENSORS = "sensors"
VS_HUMIDIFIERS = "humidifiers"
VS_NUMBERS = "numbers"
VS_BINARY_SENSORS = "binary_sensors"
VS_MANAGER = "manager"

DEV_TYPE_TO_HA = {
    "LV-PUR131S": "fan",
    "Core200S": "fan",
    "Core300S": "fan",
    "Core400S": "fan",
    "Core600S": "fan",
    "Classic200S": "humidifier",
    "Classic300S": "humidifier",
    "Dual200S": "humidifier",
    "LV600S": "humidifier",
    "OASISMIST": "humidifier",
    "ESD16": "walldimmer",
    "ESWD16": "walldimmer",
    "ESL100": "bulb-dimmable",
    "ESL100CW": "bulb-tunable-white",
    "wifi-switch-1.3": "outlet",
    "ESW03-USA": "outlet",
    "ESW01-EU": "outlet",
    "ESW15-USA": "outlet",
    "ESWL01": "switch",
    "ESWL03": "switch",
    "ESO15-TB": "outlet",
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
    "Core400S": "Core400S",
    "LAP-C401S-WJP": "Core400S",  # Alt ID Model Core400S
    "LAP-C401S-WUSR": "Core400S",  # Alt ID Model Core400S
    "LAP-C401S-WAAA": "Core400S",  # Alt ID Model Core400S
    "Core600S": "Core600S",
    "LAP-C601S-WUS": "Core600S",  # Alt ID Model Core600S
    "LAP-C601S-WUSR": "Core600S",  # Alt ID Model Core600S
    "LAP-C601S-WEU": "Core600S",  # Alt ID Model Core600S
    # Humidifiers
    "Classic200S": "Classic200S",
    "Classic300S": "Classic300S",
    "LUH-A601S-WUSB": "Classic300S",  # Alt ID Model Classic300S
    "Dual200S": "Dual200S",
    "LUH-D301S-WUSR": "Dual200S",  # Alt ID Model Dual200S
    "LUH-D301S-WJP": "Dual200S",  # Alt ID Model Dual200S
    "LUH-D301S-WEU": "Dual200S",  # Alt ID Model Dual200S
    "LV600S": "LV600S",
    "LUH-A602S-WUSR": "LV600S",  # Alt ID Model LV600S
    "LUH-A602S-WUS": "LV600S",  # Alt ID Model LV600S
    "LUH-A602S-WEUR": "LV600S",  # Alt ID Model LV600S
    "LUH-A602S-WEU": "LV600S",  # Alt ID Model LV600S
    "LUH-A602S-WJP": "LV600S",  # Alt ID Model LV600S
    "OASISMIST": "OASISMIST",
    "LUH-O451S-WUS": "OASISMIST",  # Alt ID Model OASISMIST
}
