"""Zwave workarounds."""
from . import const

# Manufacturers
FIBARO = 0x010f
PHILIO = 0x013c
WENZHOU = 0x0118
SOMFY = 0x47

# Product IDs
PHILIO_SLIM_SENSOR = 0x0002
PHILIO_3_IN_1_SENSOR_GEN_4 = 0x000d
PHILIO_PAN07 = 0x0005

# Product Types
FGFS101_FLOOD_SENSOR_TYPE = 0x0b00
FGRM222_SHUTTER2 = 0x0301
PHILIO_SWITCH = 0x0001
PHILIO_SENSOR = 0x0002
SOMFY_ZRTSI = 0x5a52

# Mapping devices
PHILIO_SLIM_SENSOR_MOTION_MTII = (PHILIO, PHILIO_SENSOR, PHILIO_SLIM_SENSOR, 0)
PHILIO_3_IN_1_SENSOR_GEN_4_MOTION_MTII = (
    PHILIO, PHILIO_SENSOR, PHILIO_3_IN_1_SENSOR_GEN_4, 0)
PHILIO_PAN07_MTII = (PHILIO, PHILIO_SWITCH, PHILIO_PAN07, 0)
WENZHOU_SLIM_SENSOR_MOTION_MTII = (
    WENZHOU, PHILIO_SENSOR, PHILIO_SLIM_SENSOR, 0)

# Workarounds
WORKAROUND_NO_OFF_EVENT = 'trigger_no_off_event'
WORKAROUND_NO_POSITION = 'workaround_no_position'
WORKAROUND_REVERSE_OPEN_CLOSE = 'reverse_open_close'
WORKAROUND_REFRESH_NODE_ON_UPDATE = 'refresh_node_on_update'
WORKAROUND_IGNORE = 'workaround_ignore'

# List of workarounds by (manufacturer_id, product_type, product_id, index)
DEVICE_MAPPINGS_MTII = {
    PHILIO_SLIM_SENSOR_MOTION_MTII: WORKAROUND_NO_OFF_EVENT,
    PHILIO_3_IN_1_SENSOR_GEN_4_MOTION_MTII: WORKAROUND_NO_OFF_EVENT,
    WENZHOU_SLIM_SENSOR_MOTION_MTII: WORKAROUND_NO_OFF_EVENT,
    PHILIO_PAN07_MTII: WORKAROUND_REFRESH_NODE_ON_UPDATE,
}

SOMFY_ZRTSI_CONTROLLER_MT = (SOMFY, SOMFY_ZRTSI)
FIBARO_FGRM222_MT = (FIBARO, FGRM222_SHUTTER2)

# List of workarounds by (manufacturer_id, product_type)
DEVICE_MAPPINGS_MT = {
    SOMFY_ZRTSI_CONTROLLER_MT: WORKAROUND_NO_POSITION,
    FIBARO_FGRM222_MT: WORKAROUND_REVERSE_OPEN_CLOSE,
}


# Component mapping devices
FIBARO_FGFS101_SENSOR_ALARM = (
    FIBARO, FGFS101_FLOOD_SENSOR_TYPE, const.COMMAND_CLASS_SENSOR_ALARM)
FIBARO_FGRM222_BINARY = (
    FIBARO, FGRM222_SHUTTER2, const.COMMAND_CLASS_SWITCH_BINARY)

# List of component workarounds by
# (manufacturer_id, product_type, command_class)
DEVICE_COMPONENT_MAPPING = {
    FIBARO_FGFS101_SENSOR_ALARM: 'binary_sensor',
    FIBARO_FGRM222_BINARY: WORKAROUND_IGNORE,
}


def get_device_component_mapping(value):
    """Get mapping of value to another component."""
    if (value.node.manufacturer_id.strip() and
            value.node.product_type.strip()):
        manufacturer_id = int(value.node.manufacturer_id, 16)
        product_type = int(value.node.product_type, 16)
        return DEVICE_COMPONENT_MAPPING.get(
            (manufacturer_id, product_type, value.command_class))

    return None


def get_device_mapping(value):
    """Get mapping of value to a workaround."""
    if (value.node.manufacturer_id.strip() and
            value.node.product_id.strip() and
            value.node.product_type.strip()):
        manufacturer_id = int(value.node.manufacturer_id, 16)
        product_type = int(value.node.product_type, 16)
        product_id = int(value.node.product_id, 16)
        result = DEVICE_MAPPINGS_MTII.get(
            (manufacturer_id, product_type, product_id, value.index))
        if result:
            return result
        return DEVICE_MAPPINGS_MT.get((manufacturer_id, product_type))

    return None
