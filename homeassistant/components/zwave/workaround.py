"""Z-Wave workarounds."""
from . import const

# Manufacturers
FIBARO = 0x010F
GE = 0x0063
PHILIO = 0x013C
SOMFY = 0x0047
WENZHOU = 0x0118
VIZIA = 0x001D

# Product IDs
GE_FAN_CONTROLLER_12730 = 0x3034
GE_FAN_CONTROLLER_14287 = 0x3131
JASCO_FAN_CONTROLLER_14314 = 0x3138
PHILIO_SLIM_SENSOR = 0x0002
PHILIO_3_IN_1_SENSOR_GEN_4 = 0x000D
PHILIO_PAN07 = 0x0005
VIZIA_FAN_CONTROLLER_VRF01 = 0x0334

# Product Types
FGFS101_FLOOD_SENSOR_TYPE = 0x0B00
FGRM222_SHUTTER2 = 0x0301
FGR222_SHUTTER2 = 0x0302
GE_DIMMER = 0x4944
PHILIO_SWITCH = 0x0001
PHILIO_SENSOR = 0x0002
SOMFY_ZRTSI = 0x5A52
VIZIA_DIMMER = 0x1001

# Mapping devices
PHILIO_SLIM_SENSOR_MOTION_MTII = (PHILIO, PHILIO_SENSOR, PHILIO_SLIM_SENSOR, 0)
PHILIO_3_IN_1_SENSOR_GEN_4_MOTION_MTII = (
    PHILIO,
    PHILIO_SENSOR,
    PHILIO_3_IN_1_SENSOR_GEN_4,
    0,
)
PHILIO_PAN07_MTI_INSTANCE = (PHILIO, PHILIO_SWITCH, PHILIO_PAN07, 1)
WENZHOU_SLIM_SENSOR_MOTION_MTII = (WENZHOU, PHILIO_SENSOR, PHILIO_SLIM_SENSOR, 0)

# Workarounds
WORKAROUND_NO_OFF_EVENT = "trigger_no_off_event"
WORKAROUND_NO_POSITION = "workaround_no_position"
WORKAROUND_REFRESH_NODE_ON_UPDATE = "refresh_node_on_update"
WORKAROUND_IGNORE = "workaround_ignore"

# List of workarounds by (manufacturer_id, product_type, product_id, index)
DEVICE_MAPPINGS_MTII = {
    PHILIO_SLIM_SENSOR_MOTION_MTII: WORKAROUND_NO_OFF_EVENT,
    PHILIO_3_IN_1_SENSOR_GEN_4_MOTION_MTII: WORKAROUND_NO_OFF_EVENT,
    WENZHOU_SLIM_SENSOR_MOTION_MTII: WORKAROUND_NO_OFF_EVENT,
}

# List of workarounds by (manufacturer_id, product_type, product_id, instance)
DEVICE_MAPPINGS_MTI_INSTANCE = {
    PHILIO_PAN07_MTI_INSTANCE: WORKAROUND_REFRESH_NODE_ON_UPDATE
}

SOMFY_ZRTSI_CONTROLLER_MT = (SOMFY, SOMFY_ZRTSI)

# List of workarounds by (manufacturer_id, product_type)
DEVICE_MAPPINGS_MT = {SOMFY_ZRTSI_CONTROLLER_MT: WORKAROUND_NO_POSITION}

# Component mapping devices
FIBARO_FGFS101_SENSOR_ALARM = (
    FIBARO,
    FGFS101_FLOOD_SENSOR_TYPE,
    const.COMMAND_CLASS_SENSOR_ALARM,
)
FIBARO_FGRM222_BINARY = (FIBARO, FGRM222_SHUTTER2, const.COMMAND_CLASS_SWITCH_BINARY)
FIBARO_FGR222_BINARY = (FIBARO, FGR222_SHUTTER2, const.COMMAND_CLASS_SWITCH_BINARY)
GE_FAN_CONTROLLER_12730_MULTILEVEL = (
    GE,
    GE_DIMMER,
    GE_FAN_CONTROLLER_12730,
    const.COMMAND_CLASS_SWITCH_MULTILEVEL,
)
GE_FAN_CONTROLLER_14287_MULTILEVEL = (
    GE,
    GE_DIMMER,
    GE_FAN_CONTROLLER_14287,
    const.COMMAND_CLASS_SWITCH_MULTILEVEL,
)
JASCO_FAN_CONTROLLER_14314_MULTILEVEL = (
    GE,
    GE_DIMMER,
    JASCO_FAN_CONTROLLER_14314,
    const.COMMAND_CLASS_SWITCH_MULTILEVEL,
)
VIZIA_FAN_CONTROLLER_VRF01_MULTILEVEL = (
    VIZIA,
    VIZIA_DIMMER,
    VIZIA_FAN_CONTROLLER_VRF01,
    const.COMMAND_CLASS_SWITCH_MULTILEVEL,
)

# List of component workarounds by
# (manufacturer_id, product_type, command_class)
DEVICE_COMPONENT_MAPPING = {
    FIBARO_FGFS101_SENSOR_ALARM: "binary_sensor",
    FIBARO_FGRM222_BINARY: WORKAROUND_IGNORE,
    FIBARO_FGR222_BINARY: WORKAROUND_IGNORE,
}

# List of component workarounds by
# (manufacturer_id, product_type, product_id, command_class)
DEVICE_COMPONENT_MAPPING_MTI = {
    GE_FAN_CONTROLLER_12730_MULTILEVEL: "fan",
    GE_FAN_CONTROLLER_14287_MULTILEVEL: "fan",
    JASCO_FAN_CONTROLLER_14314_MULTILEVEL: "fan",
    VIZIA_FAN_CONTROLLER_VRF01_MULTILEVEL: "fan",
}


def get_device_component_mapping(value):
    """Get mapping of value to another component."""
    if value.node.manufacturer_id.strip() and value.node.product_type.strip():
        manufacturer_id = int(value.node.manufacturer_id, 16)
        product_type = int(value.node.product_type, 16)
        product_id = int(value.node.product_id, 16)
        result = DEVICE_COMPONENT_MAPPING.get(
            (manufacturer_id, product_type, value.command_class)
        )
        if result:
            return result

        result = DEVICE_COMPONENT_MAPPING_MTI.get(
            (manufacturer_id, product_type, product_id, value.command_class)
        )
        if result:
            return result

    return None


def get_device_mapping(value):
    """Get mapping of value to a workaround."""
    if (
        value.node.manufacturer_id.strip()
        and value.node.product_id.strip()
        and value.node.product_type.strip()
    ):
        manufacturer_id = int(value.node.manufacturer_id, 16)
        product_type = int(value.node.product_type, 16)
        product_id = int(value.node.product_id, 16)
        result = DEVICE_MAPPINGS_MTII.get(
            (manufacturer_id, product_type, product_id, value.index)
        )
        if result:
            return result

        result = DEVICE_MAPPINGS_MTI_INSTANCE.get(
            (manufacturer_id, product_type, product_id, value.instance)
        )
        if result:
            return result

        return DEVICE_MAPPINGS_MT.get((manufacturer_id, product_type))

    return None
