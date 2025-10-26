"""Constants for the homekit_controller component."""

from aiohomekit.exceptions import (
    AccessoryDisconnectedError,
    AccessoryNotFoundError,
    EncryptionError,
)
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

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
    ServicesTypes.LIGHTBULB: "light",
    ServicesTypes.OUTLET: "switch",
    ServicesTypes.SWITCH: "switch",
    ServicesTypes.THERMOSTAT: "climate",
    ServicesTypes.HEATER_COOLER: "climate",
    ServicesTypes.SECURITY_SYSTEM: "alarm_control_panel",
    ServicesTypes.GARAGE_DOOR_OPENER: "cover",
    ServicesTypes.WINDOW: "cover",
    ServicesTypes.WINDOW_COVERING: "cover",
    ServicesTypes.LOCK_MECHANISM: "lock",
    ServicesTypes.CONTACT_SENSOR: "binary_sensor",
    ServicesTypes.MOTION_SENSOR: "binary_sensor",
    ServicesTypes.CARBON_DIOXIDE_SENSOR: "sensor",
    ServicesTypes.HUMIDITY_SENSOR: "sensor",
    ServicesTypes.HUMIDIFIER_DEHUMIDIFIER: "humidifier",
    ServicesTypes.LIGHT_SENSOR: "sensor",
    ServicesTypes.TEMPERATURE_SENSOR: "sensor",
    ServicesTypes.BATTERY_SERVICE: "sensor",
    ServicesTypes.SMOKE_SENSOR: "binary_sensor",
    ServicesTypes.CARBON_MONOXIDE_SENSOR: "binary_sensor",
    ServicesTypes.LEAK_SENSOR: "binary_sensor",
    ServicesTypes.FAN: "fan",
    ServicesTypes.FAN_V2: "fan",
    ServicesTypes.OCCUPANCY_SENSOR: "binary_sensor",
    ServicesTypes.TELEVISION: "media_player",
    ServicesTypes.FAUCET: "switch",
    ServicesTypes.VALVE: "switch",
    ServicesTypes.CAMERA_RTP_STREAM_MANAGEMENT: "camera",
    ServicesTypes.DOORBELL: "event",
    ServicesTypes.STATELESS_PROGRAMMABLE_SWITCH: "event",
    ServicesTypes.SERVICE_LABEL: "event",
    ServicesTypes.AIR_PURIFIER: "fan",
}

CHARACTERISTIC_PLATFORMS = {
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_WATT: "sensor",
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS: "sensor",
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS_20: "sensor",
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_KW_HOUR: "sensor",
    CharacteristicsTypes.VENDOR_AQARA_GATEWAY_VOLUME: "number",
    CharacteristicsTypes.VENDOR_AQARA_E1_GATEWAY_VOLUME: "number",
    CharacteristicsTypes.VENDOR_AQARA_PAIRING_MODE: "switch",
    CharacteristicsTypes.VENDOR_AQARA_E1_PAIRING_MODE: "switch",
    CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_COOL: "number",
    CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_HEAT: "number",
    CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_COOL: "number",
    CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_HEAT: "number",
    CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_COOL: "number",
    CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_HEAT: "number",
    CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE: "select",
    CharacteristicsTypes.VENDOR_EVE_ENERGY_WATT: "sensor",
    CharacteristicsTypes.VENDOR_EVE_DEGREE_AIR_PRESSURE: "sensor",
    CharacteristicsTypes.VENDOR_EVE_DEGREE_ELEVATION: "number",
    CharacteristicsTypes.VENDOR_EVE_MOTION_DURATION: "number",
    CharacteristicsTypes.VENDOR_EVE_MOTION_SENSITIVITY: "number",
    CharacteristicsTypes.VENDOR_EVE_THERMO_VALVE_POSITION: "sensor",
    CharacteristicsTypes.VENDOR_HAA_SETUP: "button",
    CharacteristicsTypes.VENDOR_HAA_UPDATE: "button",
    CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY: "sensor",
    CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY_2: "sensor",
    CharacteristicsTypes.VENDOR_VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: "number",
    CharacteristicsTypes.VENDOR_VOCOLINC_OUTLET_ENERGY: "sensor",
    CharacteristicsTypes.VENDOR_ECOBEE_CLEAR_HOLD: "button",
    CharacteristicsTypes.VENDOR_ECOBEE_FAN_WRITE_SPEED: "number",
    CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: "number",
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
    CharacteristicsTypes.THREAD_NODE_CAPABILITIES: "sensor",
    CharacteristicsTypes.THREAD_CONTROL_POINT: "button",
    CharacteristicsTypes.MUTE: "switch",
    CharacteristicsTypes.FILTER_LIFE_LEVEL: "sensor",
    CharacteristicsTypes.VENDOR_AIRVERSA_SLEEP_MODE: "switch",
    CharacteristicsTypes.TEMPERATURE_UNITS: "select",
    CharacteristicsTypes.AIR_PURIFIER_STATE_CURRENT: "sensor",
    CharacteristicsTypes.AIR_PURIFIER_STATE_TARGET: "select",
}

STARTUP_EXCEPTIONS = (
    TimeoutError,
    AccessoryNotFoundError,
    EncryptionError,
    AccessoryDisconnectedError,
)

# 10 seconds was chosen because it is soon enough
# for most state changes to happen but not too
# long that the BLE connection is dropped. It
# also happens to be the same value used by
# the update coordinator.
DEBOUNCE_COOLDOWN = 10  # seconds

SUBSCRIBE_COOLDOWN = 0.25  # seconds
