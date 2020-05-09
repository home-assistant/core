"""Map Z-Wave nodes and values to Home Assistant entities."""
import openzwavemqtt.const as const_ozw
from openzwavemqtt.const import CommandClass, ValueGenre, ValueIndex, ValueType

from . import const

DISCOVERY_SCHEMAS = (
    {  # Light
        const.DISC_COMPONENT: "light",
        const.DISC_GENERIC_DEVICE_CLASS: (
            const_ozw.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const_ozw.GENERIC_TYPE_SWITCH_REMOTE,
        ),
        const.DISC_SPECIFIC_DEVICE_CLASS: (
            const_ozw.SPECIFIC_TYPE_POWER_SWITCH_MULTILEVEL,
            const_ozw.SPECIFIC_TYPE_SCENE_SWITCH_MULTILEVEL,
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
        const.DISC_GENERIC_DEVICE_CLASS: (
            const_ozw.GENERIC_TYPE_METER,
            const_ozw.GENERIC_TYPE_SENSOR_ALARM,
            const_ozw.GENERIC_TYPE_SENSOR_BINARY,
            const_ozw.GENERIC_TYPE_SWITCH_BINARY,
            const_ozw.GENERIC_TYPE_ENTRY_CONTROL,
            const_ozw.GENERIC_TYPE_SENSOR_MULTILEVEL,
            const_ozw.GENERIC_TYPE_SWITCH_MULTILEVEL,
            const_ozw.GENERIC_TYPE_GENERIC_CONTROLLER,
            const_ozw.GENERIC_TYPE_SWITCH_REMOTE,
            const_ozw.GENERIC_TYPE_REPEATER_SLAVE,
            const_ozw.GENERIC_TYPE_THERMOSTAT,
            const_ozw.GENERIC_TYPE_WALL_CONTROLLER,
        ),
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {
                const.DISC_COMMAND_CLASS: (CommandClass.SWITCH_BINARY,),
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
    if (
        const.DISC_COMMAND_CLASS in schema
        and value.parent.command_class_id not in schema[const.DISC_COMMAND_CLASS]
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
