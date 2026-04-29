"""Constants for the Ouman EH-800 integration."""

from ouman_eh_800_api import (
    L1BaseEndpoints,
    L1RoomSensor,
    L2BaseEndpoints,
    L2RoomSensor,
    OumanEndpoint,
    SystemEndpoints,
)

DOMAIN = "ouman_eh_800"

DEFAULT_SCAN_INTERVAL_SECONDS = 60

# Sensor endpoints that should NOT be marked as DIAGNOSTIC.
# Sensors default to DIAGNOSTIC; these are the primary readings users care about.
PRIMARY_SENSOR_ENDPOINTS: frozenset[OumanEndpoint] = frozenset(
    (
        SystemEndpoints.OUTSIDE_TEMPERATURE,
        L1BaseEndpoints.SUPPLY_WATER_TEMPERATURE,
        L1BaseEndpoints.VALVE_POSITION,
        L1RoomSensor.ROOM_TEMPERATURE,
        L1RoomSensor.ROOM_TEMPERATURE_SETPOINT,
        L2BaseEndpoints.SUPPLY_WATER_TEMPERATURE,
        L2BaseEndpoints.VALVE_POSITION,
        L2RoomSensor.ROOM_TEMPERATURE,
        L2RoomSensor.ROOM_TEMPERATURE_SETPOINT,
    )
)

ENDPOINTS_DISABLED_BY_DEFAULT: frozenset[OumanEndpoint] = frozenset(
    (
        # L1
        L1BaseEndpoints.CIRCUIT_NAME,
        L1BaseEndpoints.CURVE_SUPPLY_WATER_TEMPERATURE,
        L1BaseEndpoints.FINE_ADJUSTMENT_EFFECT,
        L1BaseEndpoints.ROOM_SENSOR_INSTALLED,
        L1BaseEndpoints.TEMPERATURE_LEVEL_STATUS_TEXT,
        L1RoomSensor.DELAYED_ROOM_TEMPERATURE,
        L1RoomSensor.ROOM_SENSOR_POTENTIOMETER,
        # L2
        L2BaseEndpoints.CIRCUIT_NAME,
        L2BaseEndpoints.CURVE_SUPPLY_WATER_TEMPERATURE,
        L2BaseEndpoints.DELAYED_OUTDOOR_TEMPERATURE_EFFECT,
        L2BaseEndpoints.ROOM_SENSOR_INSTALLED,
        L2BaseEndpoints.TEMPERATURE_LEVEL_STATUS_TEXT,
        L2RoomSensor.DELAYED_ROOM_TEMPERATURE,
        # System
        SystemEndpoints.RELAY_STATUS_TEXT,
        SystemEndpoints.L2_INSTALLED_STATUS,
        SystemEndpoints.RELAY_CONFIGURATION_TYPE,
    )
)
