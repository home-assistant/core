"""Zwave util methods."""
import logging

from . import const

_LOGGER = logging.getLogger(__name__)


def check_node_schema(node, schema):
    """Check if node matches the passed node schema."""
    if (const.DISC_NODE_ID in schema and
            node.node_id not in schema[const.DISC_NODE_ID]):
        _LOGGER.debug("node.node_id %s not in node_id %s",
                      node.node_id, schema[const.DISC_NODE_ID])
        return False
    if (const.DISC_GENERIC_DEVICE_CLASS in schema and
            node.generic not in schema[const.DISC_GENERIC_DEVICE_CLASS]):
        _LOGGER.debug("node.generic %s not in generic_device_class %s",
                      node.generic, schema[const.DISC_GENERIC_DEVICE_CLASS])
        return False
    if (const.DISC_SPECIFIC_DEVICE_CLASS in schema and
            node.specific not in schema[const.DISC_SPECIFIC_DEVICE_CLASS]):
        _LOGGER.debug("node.specific %s not in specific_device_class %s",
                      node.specific, schema[const.DISC_SPECIFIC_DEVICE_CLASS])
        return False
    return True


def check_value_schema(value, schema):
    """Check if the value matches the passed value schema."""
    if (const.DISC_COMMAND_CLASS in schema and
            value.command_class not in schema[const.DISC_COMMAND_CLASS]):
        _LOGGER.debug("value.command_class %s not in command_class %s",
                      value.command_class, schema[const.DISC_COMMAND_CLASS])
        return False
    if (const.DISC_TYPE in schema and
            value.type not in schema[const.DISC_TYPE]):
        _LOGGER.debug("value.type %s not in type %s",
                      value.type, schema[const.DISC_TYPE])
        return False
    if (const.DISC_GENRE in schema and
            value.genre not in schema[const.DISC_GENRE]):
        _LOGGER.debug("value.genre %s not in genre %s",
                      value.genre, schema[const.DISC_GENRE])
        return False
    if (const.DISC_READONLY in schema and
            value.is_read_only is not schema[const.DISC_READONLY]):
        _LOGGER.debug("value.is_read_only %s not %s",
                      value.is_read_only, schema[const.DISC_READONLY])
        return False
    if (const.DISC_WRITEONLY in schema and
            value.is_write_only is not schema[const.DISC_WRITEONLY]):
        _LOGGER.debug("value.is_write_only %s not %s",
                      value.is_write_only, schema[const.DISC_WRITEONLY])
        return False
    if (const.DISC_LABEL in schema and
            value.label not in schema[const.DISC_LABEL]):
        _LOGGER.debug("value.label %s not in label %s",
                      value.label, schema[const.DISC_LABEL])
        return False
    if (const.DISC_INDEX in schema and
            value.index not in schema[const.DISC_INDEX]):
        _LOGGER.debug("value.index %s not in index %s",
                      value.index, schema[const.DISC_INDEX])
        return False
    if (const.DISC_INSTANCE in schema and
            value.instance not in schema[const.DISC_INSTANCE]):
        _LOGGER.debug("value.instance %s not in instance %s",
                      value.instance, schema[const.DISC_INSTANCE])
        return False
    return True


def node_name(node):
    """Return the name of the node."""
    return node.name or '{} {}'.format(
        node.manufacturer_name, node.product_name)
