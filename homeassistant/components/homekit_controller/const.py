"""Constants for the homekit_controller component."""
from aiohomekit.model.characteristics import CharacteristicsTypes

DOMAIN = "homekit_controller"

KNOWN_DEVICES = f"{DOMAIN}-devices"
CONTROLLER = f"{DOMAIN}-controller"
ENTITY_MAP = f"{DOMAIN}-entity-map"
TRIGGERS = f"{DOMAIN}-triggers"

HOMEKIT_DIR = ".homekit"
PAIRING_FILE = "pairing.json"

# Mapping from Homekit type to component.
HOMEKIT_ACCESSORY_DISPATCH = {
    "lightbulb": "light",
    "outlet": "switch",
    "switch": "switch",
    "thermostat": "climate",
    "heater-cooler": "climate",
    "security-system": "alarm_control_panel",
    "garage-door-opener": "cover",
    "window": "cover",
    "window-covering": "cover",
    "lock-mechanism": "lock",
    "contact": "binary_sensor",
    "motion": "binary_sensor",
    "carbon-dioxide": "sensor",
    "humidity": "sensor",
    "humidifier-dehumidifier": "humidifier",
    "light": "sensor",
    "temperature": "sensor",
    "battery": "sensor",
    "smoke": "binary_sensor",
    "carbon-monoxide": "binary_sensor",
    "leak": "binary_sensor",
    "fan": "fan",
    "fanv2": "fan",
    "air-quality": "air_quality",
    "occupancy": "binary_sensor",
    "television": "media_player",
    "valve": "switch",
    "camera-rtp-stream-management": "camera",
}

CHARACTERISTIC_PLATFORMS = {
    CharacteristicsTypes.Vendor.EVE_ENERGY_WATT: "sensor",
    CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY: "sensor",
    CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY_2: "sensor",
    CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: "number",
    CharacteristicsTypes.get_uuid(CharacteristicsTypes.TEMPERATURE_CURRENT): "sensor",
    CharacteristicsTypes.get_uuid(
        CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT
    ): "sensor",
}
