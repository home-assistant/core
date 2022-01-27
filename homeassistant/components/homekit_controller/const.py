"""Constants for the homekit_controller component."""
from aiohomekit.model.characteristics import CharacteristicsTypes

DOMAIN = "homekit_controller"

KNOWN_DEVICES = f"{DOMAIN}-devices"
CONTROLLER = f"{DOMAIN}-controller"
ENTITY_MAP = f"{DOMAIN}-entity-map"
TRIGGERS = f"{DOMAIN}-triggers"

HOMEKIT_DIR = ".homekit"
PAIRING_FILE = "pairing.json"

IDENTIFIER_SERIAL_NUMBER = "homekit_controller:serial-number"
IDENTIFIER_ACCESSORY_ID = "homekit_controller:accessory-id"
IDENTIFIER_LEGACY_SERIAL_NUMBER = "serial-number"
IDENTIFIER_LEGACY_ACCESSORY_ID = "accessory-id"

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
    "occupancy": "binary_sensor",
    "television": "media_player",
    "valve": "switch",
    "camera-rtp-stream-management": "camera",
}

CHARACTERISTIC_PLATFORMS = {
    CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_WATT: "sensor",
    CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_AMPS: "sensor",
    CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_AMPS_20: "sensor",
    CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_KW_HOUR: "sensor",
    CharacteristicsTypes.Vendor.AQARA_GATEWAY_VOLUME: "number",
    CharacteristicsTypes.Vendor.AQARA_E1_GATEWAY_VOLUME: "number",
    CharacteristicsTypes.Vendor.AQARA_PAIRING_MODE: "switch",
    CharacteristicsTypes.Vendor.AQARA_E1_PAIRING_MODE: "switch",
    CharacteristicsTypes.Vendor.ECOBEE_HOME_TARGET_COOL: "number",
    CharacteristicsTypes.Vendor.ECOBEE_HOME_TARGET_HEAT: "number",
    CharacteristicsTypes.Vendor.ECOBEE_SLEEP_TARGET_COOL: "number",
    CharacteristicsTypes.Vendor.ECOBEE_SLEEP_TARGET_HEAT: "number",
    CharacteristicsTypes.Vendor.ECOBEE_AWAY_TARGET_COOL: "number",
    CharacteristicsTypes.Vendor.ECOBEE_AWAY_TARGET_HEAT: "number",
    CharacteristicsTypes.Vendor.EVE_ENERGY_WATT: "sensor",
    CharacteristicsTypes.Vendor.EVE_DEGREE_AIR_PRESSURE: "sensor",
    CharacteristicsTypes.Vendor.EVE_DEGREE_ELEVATION: "number",
    CharacteristicsTypes.Vendor.HAA_SETUP: "button",
    CharacteristicsTypes.Vendor.HAA_UPDATE: "button",
    CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY: "sensor",
    CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY_2: "sensor",
    CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: "number",
    CharacteristicsTypes.Vendor.VOCOLINC_OUTLET_ENERGY: "sensor",
    CharacteristicsTypes.TEMPERATURE_CURRENT: "sensor",
    CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: "sensor",
    CharacteristicsTypes.AIR_QUALITY: "sensor",
    CharacteristicsTypes.DENSITY_PM25: "sensor",
    CharacteristicsTypes.DENSITY_PM10: "sensor",
    CharacteristicsTypes.DENSITY_OZONE: "sensor",
    CharacteristicsTypes.DENSITY_NO2: "sensor",
    CharacteristicsTypes.DENSITY_SO2: "sensor",
    CharacteristicsTypes.DENSITY_VOC: "sensor",
    CharacteristicsTypes.IDENTIFY: "button",
}

# For legacy reasons, "built-in" characteristic types are in their short form
# And vendor types don't have a short form
# This means long and short forms get mixed up in this dict, and comparisons
# don't work!
# We call get_uuid on *every* type to normalise them to the long form
# Eventually aiohomekit will use the long form exclusively amd this can be removed.
for k, v in list(CHARACTERISTIC_PLATFORMS.items()):
    value = CHARACTERISTIC_PLATFORMS.pop(k)
    CHARACTERISTIC_PLATFORMS[CharacteristicsTypes.get_uuid(k)] = value
