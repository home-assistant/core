"""Constants for the MELCloud Climate integration."""

DOMAIN = "melcloud"

CONF_POSITION = "position"
CONF_ZONE_1_TARGET_HEAT_TEMPERATURE = "temperature"
CONF_ZONE_1_TARGET_HEAT_FLOW_TEMPERATURE = "temperature"

ATTR_STATUS = "status"
ATTR_VANE_HORIZONTAL = "vane_horizontal"
ATTR_VANE_HORIZONTAL_POSITIONS = "vane_horizontal_positions"
ATTR_VANE_VERTICAL = "vane_vertical"
ATTR_VANE_VERTICAL_POSITIONS = "vane_vertical_positions"

SERVICE_SET_VANE_HORIZONTAL = "set_vane_horizontal"
SERVICE_SET_VANE_VERTICAL = "set_vane_vertical"
SERVICE_SET_ZONE_1_TARGET_HEAT_TEMPERATURE = "set_zone_1_target_heat_temperature"
SERVICE_SET_ZONE_1_TARGET_HEAT_FLOW_TEMPERATURE = (
    "set_zone_1_target_heat_flow_temperature"
)
