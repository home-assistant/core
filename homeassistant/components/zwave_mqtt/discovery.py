"""Map Z-Wave nodes and values to Home Assistant entities."""

import logging

from openzwavemqtt.const import CommandClass, ValueGenre, ValueIndex, ValueType

from . import const

_LOGGER = logging.getLogger(__name__)

DISCOVERY_SCHEMAS = [
    {  # Binary sensors
        const.DISC_COMPONENT: "binary_sensor",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_ENTRY_CONTROL,
            const.GENERIC_TYPE_SENSOR_ALARM,
            const.GENERIC_TYPE_SENSOR_BINARY,
            const.GENERIC_TYPE_SWITCH_BINARY,
            const.GENERIC_TYPE_METER,
            const.GENERIC_TYPE_SENSOR_MULTILEVEL,
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_THERMOSTAT,
            const.GENERIC_TYPE_SENSOR_NOTIFICATION,
        ],
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.SENSOR_BINARY],
                const.DISC_TYPE: ValueType.BOOL,
                const.DISC_GENRE: ValueGenre.USER,
            },
            "off_delay": {
                const.DISC_COMMAND_CLASS: [CommandClass.CONFIGURATION],
                const.DISC_INDEX: [9],
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # Notification CommandClass translates to binary_sensor
        const.DISC_COMPONENT: "binary_sensor",
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.NOTIFICATION],
                const.DISC_GENRE: ValueGenre.USER,
                const.DISC_TYPE: [ValueType.BOOL, ValueType.LIST],
            }
        },
    },
    {  # Thermostat translates to climate
        const.DISC_COMPONENT: "climate",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_THERMOSTAT,
            const.GENERIC_TYPE_SENSOR_MULTILEVEL,
        ],
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.THERMOSTAT_SETPOINT]
            },
            "temperature": {
                const.DISC_COMMAND_CLASS: [CommandClass.SENSOR_MULTILEVEL],
                const.DISC_INDEX: [ValueIndex.SENSOR_MULTILEVEL_TEMPERATURE],
                const.DISC_OPTIONAL: True,
            },
            "mode": {
                const.DISC_COMMAND_CLASS: [CommandClass.THERMOSTAT_MODE],
                const.DISC_OPTIONAL: True,
            },
            "fan_mode": {
                const.DISC_COMMAND_CLASS: [CommandClass.THERMOSTAT_FAN_MODE],
                const.DISC_OPTIONAL: True,
            },
            "operating_state": {
                const.DISC_COMMAND_CLASS: [CommandClass.THERMOSTAT_OPERATING_STATE],
                const.DISC_OPTIONAL: True,
            },
            "fan_action": {
                const.DISC_COMMAND_CLASS: [CommandClass.THERMOSTAT_FAN_STATE],
                const.DISC_OPTIONAL: True,
            },
            "zxt_120_swing_mode": {
                const.DISC_COMMAND_CLASS: [CommandClass.CONFIGURATION],
                const.DISC_INDEX: [33],
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # Rollershutter
        const.DISC_COMPONENT: "cover",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_ENTRY_CONTROL,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_MOTOR_MULTIPOSITION,
            const.SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
            const.SPECIFIC_TYPE_SECURE_DOOR,
        ],
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_MULTILEVEL],
                const.DISC_INDEX: [ValueIndex.SWITCH_MULTILEVEL_LEVEL],
                const.DISC_GENRE: ValueGenre.USER,
            },
            "open": {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_MULTILEVEL],
                const.DISC_INDEX: [ValueIndex.SWITCH_MULTILEVEL_BRIGHT],
                const.DISC_OPTIONAL: True,
            },
            "close": {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_MULTILEVEL],
                const.DISC_INDEX: [ValueIndex.SWITCH_MULTILEVEL_DIM],
                const.DISC_OPTIONAL: True,
            },
            "fgrm222_slat_position": {
                const.DISC_COMMAND_CLASS: [CommandClass.MANUFACTURER_PROPRIETARY],
                const.DISC_INDEX: [0],
                const.DISC_OPTIONAL: True,
            },
            "fgrm222_tilt_position": {
                const.DISC_COMMAND_CLASS: [CommandClass.MANUFACTURER_PROPRIETARY],
                const.DISC_INDEX: [1],
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # Garage Door Switch
        const.DISC_COMPONENT: "cover",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_ENTRY_CONTROL,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_MOTOR_MULTIPOSITION,
            const.SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
            const.SPECIFIC_TYPE_SECURE_DOOR,
        ],
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_BINARY],
                const.DISC_GENRE: ValueGenre.USER,
            }
        },
    },
    {  # Garage Door Barrier
        const.DISC_COMPONENT: "cover",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_ENTRY_CONTROL,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_CLASS_A_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_B_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_CLASS_C_MOTOR_CONTROL,
            const.SPECIFIC_TYPE_MOTOR_MULTIPOSITION,
            const.SPECIFIC_TYPE_SECURE_BARRIER_ADDON,
            const.SPECIFIC_TYPE_SECURE_DOOR,
        ],
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.BARRIER_OPERATOR],
                const.DISC_INDEX: [ValueIndex.BARRIER_OPERATOR_LABEL],
            }
        },
    },
    {  # Fan
        const.DISC_COMPONENT: "fan",
        const.DISC_GENERIC_DEVICE_CLASS: [const.GENERIC_TYPE_SWITCH_MULTILEVEL],
        const.DISC_SPECIFIC_DEVICE_CLASS: [const.SPECIFIC_TYPE_FAN_SWITCH],
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_MULTILEVEL],
                const.DISC_INDEX: [ValueIndex.SWITCH_MULTILEVEL_LEVEL],
                const.DISC_TYPE: ValueType.BYTE,
            }
        },
    },
    {  # Light
        const.DISC_COMPONENT: "light",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_SWITCH_REMOTE,
        ],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_POWER_SWITCH_MULTILEVEL,
            const.SPECIFIC_TYPE_SCENE_SWITCH_MULTILEVEL,
            const.SPECIFIC_TYPE_NOT_USED,
        ],
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_MULTILEVEL],
                const.DISC_INDEX: [ValueIndex.SWITCH_MULTILEVEL_LEVEL],
                const.DISC_TYPE: ValueType.BYTE,
            },
            "dimming_duration": {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_MULTILEVEL],
                const.DISC_INDEX: [ValueIndex.SWITCH_MULTILEVEL_DURATION],
                const.DISC_OPTIONAL: True,
            },
            "color": {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_COLOR],
                const.DISC_INDEX: [ValueIndex.SWITCH_COLOR_COLOR],
                const.DISC_OPTIONAL: True,
            },
            "color_channels": {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_COLOR],
                const.DISC_INDEX: [ValueIndex.SWITCH_COLOR_CHANNELS],
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # Lock
        const.DISC_COMPONENT: "lock",
        const.DISC_GENERIC_DEVICE_CLASS: [const.GENERIC_TYPE_ENTRY_CONTROL],
        const.DISC_SPECIFIC_DEVICE_CLASS: [
            const.SPECIFIC_TYPE_DOOR_LOCK,
            const.SPECIFIC_TYPE_ADVANCED_DOOR_LOCK,
            const.SPECIFIC_TYPE_SECURE_KEYPAD_DOOR_LOCK,
            const.SPECIFIC_TYPE_SECURE_LOCKBOX,
        ],
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.DOOR_LOCK],
                const.DISC_INDEX: [ValueIndex.DOOR_LOCK_LOCK],
            },
            "access_control": {
                const.DISC_COMMAND_CLASS: [CommandClass.ALARM],
                const.DISC_INDEX: [ValueIndex.ALARM_ACCESS_CONTROL],
                const.DISC_OPTIONAL: True,
            },
            "alarm_type": {
                const.DISC_COMMAND_CLASS: [CommandClass.ALARM],
                const.DISC_INDEX: [ValueIndex.ALARM_TYPE],
                const.DISC_OPTIONAL: True,
            },
            "alarm_level": {
                const.DISC_COMMAND_CLASS: [CommandClass.ALARM],
                const.DISC_INDEX: [ValueIndex.ALARM_LEVEL],
                const.DISC_OPTIONAL: True,
            },
            "v2btze_advanced": {
                const.DISC_COMMAND_CLASS: [CommandClass.CONFIGURATION],
                const.DISC_INDEX: [12],
                const.DISC_OPTIONAL: True,
            },
        },
    },
    {  # All other text/numeric sensors
        const.DISC_COMPONENT: "sensor",
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [
                    CommandClass.SENSOR_MULTILEVEL,
                    CommandClass.METER,
                    CommandClass.ALARM,
                    CommandClass.SENSOR_ALARM,
                    CommandClass.INDICATOR,
                    CommandClass.BATTERY,
                    CommandClass.NOTIFICATION,
                    CommandClass.BASIC,
                ],
                const.DISC_TYPE: [
                    ValueType.DECIMAL,
                    ValueType.INT,
                    ValueType.STRING,
                    ValueType.BYTE,
                    ValueType.LIST,
                ],
            }
        },
    },
    {  # Switch platform
        const.DISC_COMPONENT: "switch",
        const.DISC_GENERIC_DEVICE_CLASS: [
            const.GENERIC_TYPE_METER,
            const.GENERIC_TYPE_SENSOR_ALARM,
            const.GENERIC_TYPE_SENSOR_BINARY,
            const.GENERIC_TYPE_SWITCH_BINARY,
            const.GENERIC_TYPE_ENTRY_CONTROL,
            const.GENERIC_TYPE_SENSOR_MULTILEVEL,
            const.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const.GENERIC_TYPE_GENERIC_CONTROLLER,
            const.GENERIC_TYPE_SWITCH_REMOTE,
            const.GENERIC_TYPE_REPEATER_SLAVE,
            const.GENERIC_TYPE_THERMOSTAT,
            const.GENERIC_TYPE_WALL_CONTROLLER,
        ],
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: [CommandClass.SWITCH_BINARY],
                const.DISC_TYPE: ValueType.BOOL,
                const.DISC_GENRE: ValueGenre.USER,
            }
        },
    },
]


def check_node_schema(node, schema):
    """Check if node matches the passed node schema."""
    if const.DISC_NODE_ID in schema and node.node_id not in schema[const.DISC_NODE_ID]:
        return False
    if (
        const.DISC_GENERIC_DEVICE_CLASS in schema
        and node.node_generic
        not in ensure_list(schema[const.DISC_GENERIC_DEVICE_CLASS])
    ):
        return False
    if (
        const.DISC_SPECIFIC_DEVICE_CLASS in schema
        and node.node_specific
        not in ensure_list(schema[const.DISC_SPECIFIC_DEVICE_CLASS])
    ):
        return False
    return True


def check_value_schema(value, schema):
    """Check if the value matches the passed value schema."""
    if (
        const.DISC_COMMAND_CLASS in schema
        and value.parent.command_class_id not in schema[const.DISC_COMMAND_CLASS]
    ):
        return False
    if const.DISC_TYPE in schema and value.type not in ensure_list(
        schema[const.DISC_TYPE]
    ):
        return False
    if const.DISC_GENRE in schema and value.genre not in ensure_list(
        schema[const.DISC_GENRE]
    ):
        return False
    if const.DISC_INDEX in schema and value.index not in ensure_list(
        schema[const.DISC_INDEX]
    ):
        return False
    if const.DISC_INSTANCE in schema and value.instance not in ensure_list(
        schema[const.DISC_INSTANCE]
    ):
        return False
    if const.DISC_SCHEMAS in schema:
        found = False
        for schema_item in schema[const.DISC_SCHEMAS]:
            found = found or check_value_schema(value, schema_item)
        if not found:
            return False

    return True


def ensure_list(value):
    """Convert a value to a list if needed."""
    if isinstance(value, list):
        return value
    return [value]
