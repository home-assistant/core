"""Map Z-Wave nodes and values to Home Assistant entities."""
from openzwavemqtt.const import CommandClass, ValueGenre, ValueType

from . import const

DISCOVERY_SCHEMAS = [
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
