"""Map Z-Wave nodes and values to Home Assistant entities."""
import openzwavemqtt.const as const_ozw
from openzwavemqtt.const import CommandClass, ValueGenre, ValueIndex, ValueType

from . import const

DISCOVERY_SCHEMAS = (
    {  # Binary sensors
        const.DISC_COMPONENT: "binary_sensor",
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: CommandClass.SENSOR_BINARY,
                const.DISC_TYPE: ValueType.BOOL,
                const.DISC_GENRE: ValueGenre.USER,
            },
            "off_delay": {
                const.DISC_COMMAND_CLASS: CommandClass.CONFIGURATION,
                const.DISC_INDEX: 9,
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # Notification CommandClass translates to binary_sensor
        const.DISC_COMPONENT: "binary_sensor",
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: CommandClass.NOTIFICATION,
                const.DISC_GENRE: ValueGenre.USER,
                const.DISC_TYPE: (ValueType.BOOL, ValueType.LIST),
            }
        },
    },
    {  # Z-Wave Thermostat device translates to Climate entity
        const.DISC_COMPONENT: "climate",
        const.DISC_GENERIC_DEVICE_CLASS: (
            const_ozw.GENERIC_TYPE_THERMOSTAT,
            const_ozw.GENERIC_TYPE_SENSOR_MULTILEVEL,
        ),
        const.DISC_SPECIFIC_DEVICE_CLASS: (
            const_ozw.SPECIFIC_TYPE_THERMOSTAT_GENERAL,
            const_ozw.SPECIFIC_TYPE_THERMOSTAT_GENERAL_V2,
            const_ozw.SPECIFIC_TYPE_SETBACK_THERMOSTAT,
            const_ozw.SPECIFIC_TYPE_THERMOSTAT_HEATING,
            const_ozw.SPECIFIC_TYPE_SETPOINT_THERMOSTAT,
            const_ozw.SPECIFIC_TYPE_NOT_USED,
        ),
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_MODE,)
            },
            "mode": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_MODE,),
                const.DISC_OPTIONAL: True,
            },
            "temperature": {
                const.DISC_COMMAND_CLASS: (CommandClass.SENSOR_MULTILEVEL,),
                const.DISC_INDEX: (1,),
                const.DISC_OPTIONAL: True,
            },
            "fan_mode": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_FAN_MODE,),
                const.DISC_OPTIONAL: True,
            },
            "operating_state": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_OPERATING_STATE,),
                const.DISC_OPTIONAL: True,
            },
            "fan_action": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_FAN_STATE,),
                const.DISC_OPTIONAL: True,
            },
            "valve_position": {
                const.DISC_COMMAND_CLASS: (CommandClass.SWITCH_MULTILEVEL,),
                const.DISC_INDEX: (0,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_heating": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (1,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_cooling": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (2,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_furnace": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (7,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_dry_air": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (8,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_moist_air": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (9,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_auto_changeover": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (10,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_eco_heating": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (11,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_eco_cooling": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (12,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_away_heating": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (13,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_away_cooling": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (14,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_full_power": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (15,),
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # Z-Wave Thermostat device without mode support
        const.DISC_COMPONENT: "climate",
        const.DISC_GENERIC_DEVICE_CLASS: (const_ozw.GENERIC_TYPE_THERMOSTAT,),
        const.DISC_SPECIFIC_DEVICE_CLASS: (
            const_ozw.SPECIFIC_TYPE_SETPOINT_THERMOSTAT,
        ),
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,)
            },
            "temperature": {
                const.DISC_COMMAND_CLASS: (CommandClass.SENSOR_MULTILEVEL,),
                const.DISC_INDEX: (1,),
                const.DISC_OPTIONAL: True,
            },
            "operating_state": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_OPERATING_STATE,),
                const.DISC_OPTIONAL: True,
            },
            "valve_position": {
                const.DISC_COMMAND_CLASS: (CommandClass.SWITCH_MULTILEVEL,),
                const.DISC_INDEX: (0,),
                const.DISC_OPTIONAL: True,
            },
            "setpoint_heating": {
                const.DISC_COMMAND_CLASS: (CommandClass.THERMOSTAT_SETPOINT,),
                const.DISC_INDEX: (1,),
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # Rollershutter
        const.DISC_COMPONENT: "cover",
        const.DISC_GENERIC_DEVICE_CLASS: (const_ozw.GENERIC_TYPE_SWITCH_MULTILEVEL,),
        const.DISC_SPECIFIC_DEVICE_CLASS: (
            const_ozw.SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL,
            const_ozw.SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL,
            const_ozw.SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL,
            const_ozw.SPECIFIC_TYPE_MOTOR_MULTIPOSITION,
            const_ozw.SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
            const_ozw.SPECIFIC_TYPE_SECURE_DOOR,
        ),
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: CommandClass.SWITCH_MULTILEVEL,
                const.DISC_INDEX: ValueIndex.SWITCH_MULTILEVEL_LEVEL,
                const.DISC_GENRE: ValueGenre.USER,
            },
            "open": {
                const.DISC_COMMAND_CLASS: CommandClass.SWITCH_MULTILEVEL,
                const.DISC_INDEX: ValueIndex.SWITCH_MULTILEVEL_BRIGHT,
                const.DISC_OPTIONAL: True,
            },
            "close": {
                const.DISC_COMMAND_CLASS: CommandClass.SWITCH_MULTILEVEL,
                const.DISC_INDEX: ValueIndex.SWITCH_MULTILEVEL_DIM,
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # Garage Door Barrier
        const.DISC_COMPONENT: "cover",
        const.DISC_GENERIC_DEVICE_CLASS: (const_ozw.GENERIC_TYPE_ENTRY_CONTROL,),
        const.DISC_SPECIFIC_DEVICE_CLASS: (
            const_ozw.SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
        ),
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: CommandClass.BARRIER_OPERATOR,
                const.DISC_INDEX: ValueIndex.BARRIER_OPERATOR_LABEL,
            },
        },
    },
    {  # Fan
        const.DISC_COMPONENT: "fan",
        const.DISC_GENERIC_DEVICE_CLASS: const_ozw.GENERIC_TYPE_SWITCH_MULTILEVEL,
        const.DISC_SPECIFIC_DEVICE_CLASS: const_ozw.SPECIFIC_TYPE_FAN_SWITCH,
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: CommandClass.SWITCH_MULTILEVEL,
                const.DISC_INDEX: ValueIndex.SWITCH_MULTILEVEL_LEVEL,
                const.DISC_TYPE: ValueType.BYTE,
            },
        },
    },
    {  # Light
        const.DISC_COMPONENT: "light",
        const.DISC_GENERIC_DEVICE_CLASS: (
            const_ozw.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const_ozw.GENERIC_TYPE_SWITCH_REMOTE,
        ),
        const.DISC_SPECIFIC_DEVICE_CLASS: (
            const_ozw.SPECIFIC_TYPE_POWER_SWITCH_MULTILEVEL,
            const_ozw.SPECIFIC_TYPE_SCENE_SWITCH_MULTILEVEL,
            const_ozw.SPECIFIC_TYPE_COLOR_TUNABLE_BINARY,
            const_ozw.SPECIFIC_TYPE_COLOR_TUNABLE_MULTILEVEL,
            const_ozw.SPECIFIC_TYPE_NOT_USED,
        ),
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: (CommandClass.SWITCH_MULTILEVEL,),
                const.DISC_INDEX: ValueIndex.SWITCH_MULTILEVEL_LEVEL,
                const.DISC_TYPE: ValueType.BYTE,
            },
            "dimming_duration": {
                const.DISC_COMMAND_CLASS: (CommandClass.SWITCH_MULTILEVEL,),
                const.DISC_INDEX: ValueIndex.SWITCH_MULTILEVEL_DURATION,
                const.DISC_OPTIONAL: True,
            },
            "color": {
                const.DISC_COMMAND_CLASS: (CommandClass.SWITCH_COLOR,),
                const.DISC_INDEX: ValueIndex.SWITCH_COLOR_COLOR,
                const.DISC_OPTIONAL: True,
            },
            "color_channels": {
                const.DISC_COMMAND_CLASS: (CommandClass.SWITCH_COLOR,),
                const.DISC_INDEX: ValueIndex.SWITCH_COLOR_CHANNELS,
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # All other text/numeric sensors
        const.DISC_COMPONENT: "sensor",
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: (
                    CommandClass.SENSOR_MULTILEVEL,
                    CommandClass.METER,
                    CommandClass.ALARM,
                    CommandClass.SENSOR_ALARM,
                    CommandClass.INDICATOR,
                    CommandClass.BATTERY,
                    CommandClass.NOTIFICATION,
                    CommandClass.BASIC,
                ),
                const.DISC_TYPE: (
                    ValueType.DECIMAL,
                    ValueType.INT,
                    ValueType.STRING,
                    ValueType.BYTE,
                    ValueType.LIST,
                ),
            }
        },
    },
    {  # Switch platform
        const.DISC_COMPONENT: "switch",
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: (CommandClass.SWITCH_BINARY,),
                const.DISC_TYPE: ValueType.BOOL,
                const.DISC_GENRE: ValueGenre.USER,
            }
        },
    },
    {  # Lock platform
        const.DISC_COMPONENT: "lock",
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: (CommandClass.DOOR_LOCK,),
                const.DISC_TYPE: ValueType.BOOL,
                const.DISC_GENRE: ValueGenre.USER,
            }
        },
    },
)


def check_node_schema(node, schema):
    """Check if node matches the passed node schema."""
    if const.DISC_NODE_ID in schema and node.node_id not in schema[const.DISC_NODE_ID]:
        return False
    if const.DISC_GENERIC_DEVICE_CLASS in schema and not eq_or_in(
        node.node_generic, schema[const.DISC_GENERIC_DEVICE_CLASS]
    ):
        return False
    if const.DISC_SPECIFIC_DEVICE_CLASS in schema and not eq_or_in(
        node.node_specific, schema[const.DISC_SPECIFIC_DEVICE_CLASS]
    ):
        return False
    return True


def check_value_schema(value, schema):
    """Check if the value matches the passed value schema."""
    if const.DISC_COMMAND_CLASS in schema and not eq_or_in(
        value.parent.command_class_id, schema[const.DISC_COMMAND_CLASS]
    ):
        return False
    if const.DISC_TYPE in schema and not eq_or_in(value.type, schema[const.DISC_TYPE]):
        return False
    if const.DISC_GENRE in schema and not eq_or_in(
        value.genre, schema[const.DISC_GENRE]
    ):
        return False
    if const.DISC_INDEX in schema and not eq_or_in(
        value.index, schema[const.DISC_INDEX]
    ):
        return False
    if const.DISC_INSTANCE in schema and not eq_or_in(
        value.instance, schema[const.DISC_INSTANCE]
    ):
        return False
    if const.DISC_SCHEMAS in schema:
        found = False
        for schema_item in schema[const.DISC_SCHEMAS]:
            found = found or check_value_schema(value, schema_item)
        if not found:
            return False

    return True


def eq_or_in(val, options):
    """Return True if options contains value or if value is equal to options."""
    return val in options if isinstance(options, tuple) else val == options
