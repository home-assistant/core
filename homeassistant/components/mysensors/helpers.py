"""Helper functions for mysensors package."""
from collections import defaultdict
import logging

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util.decorator import Registry

from .const import ATTR_DEVICES, DOMAIN, FLAT_PLATFORM_TYPES, TYPE_TO_PLATFORMS

_LOGGER = logging.getLogger(__name__)
SCHEMAS = Registry()


@callback
def discover_mysensors_platform(hass, hass_config, platform, new_devices):
    """Discover a MySensors platform."""
    task = hass.async_create_task(discovery.async_load_platform(
        hass, platform, DOMAIN,
        {ATTR_DEVICES: new_devices, CONF_NAME: DOMAIN}, hass_config))
    return task


def default_schema(gateway, child, value_type_name):
    """Return a default validation schema for value types."""
    schema = {value_type_name: cv.string}
    return get_child_schema(gateway, child, value_type_name, schema)


@SCHEMAS.register(('light', 'V_DIMMER'))
def light_dimmer_schema(gateway, child, value_type_name):
    """Return a validation schema for V_DIMMER."""
    schema = {'V_DIMMER': cv.string, 'V_LIGHT': cv.string}
    return get_child_schema(gateway, child, value_type_name, schema)


@SCHEMAS.register(('light', 'V_PERCENTAGE'))
def light_percentage_schema(gateway, child, value_type_name):
    """Return a validation schema for V_PERCENTAGE."""
    schema = {'V_PERCENTAGE': cv.string, 'V_STATUS': cv.string}
    return get_child_schema(gateway, child, value_type_name, schema)


@SCHEMAS.register(('light', 'V_RGB'))
def light_rgb_schema(gateway, child, value_type_name):
    """Return a validation schema for V_RGB."""
    schema = {'V_RGB': cv.string, 'V_STATUS': cv.string}
    return get_child_schema(gateway, child, value_type_name, schema)


@SCHEMAS.register(('light', 'V_RGBW'))
def light_rgbw_schema(gateway, child, value_type_name):
    """Return a validation schema for V_RGBW."""
    schema = {'V_RGBW': cv.string, 'V_STATUS': cv.string}
    return get_child_schema(gateway, child, value_type_name, schema)


@SCHEMAS.register(('switch', 'V_IR_SEND'))
def switch_ir_send_schema(gateway, child, value_type_name):
    """Return a validation schema for V_IR_SEND."""
    schema = {'V_IR_SEND': cv.string, 'V_LIGHT': cv.string}
    return get_child_schema(gateway, child, value_type_name, schema)


def get_child_schema(gateway, child, value_type_name, schema):
    """Return a child schema."""
    set_req = gateway.const.SetReq
    child_schema = child.get_schema(gateway.protocol_version)
    schema = child_schema.extend(
        {vol.Required(
            set_req[name].value, msg=invalid_msg(gateway, child, name)):
         child_schema.schema.get(set_req[name].value, valid)
         for name, valid in schema.items()},
        extra=vol.ALLOW_EXTRA)
    return schema


def invalid_msg(gateway, child, value_type_name):
    """Return a message for an invalid child during schema validation."""
    pres = gateway.const.Presentation
    set_req = gateway.const.SetReq
    return "{} requires value_type {}".format(
        pres(child.type).name, set_req[value_type_name].name)


def validate_set_msg(msg):
    """Validate a set message."""
    if not validate_node(msg.gateway, msg.node_id):
        return {}
    child = msg.gateway.sensors[msg.node_id].children[msg.child_id]
    return validate_child(msg.gateway, msg.node_id, child, msg.sub_type)


def validate_node(gateway, node_id):
    """Validate a node."""
    if gateway.sensors[node_id].sketch_name is None:
        _LOGGER.debug("Node %s is missing sketch name", node_id)
        return False
    return True


def validate_child(gateway, node_id, child, value_type=None):
    """Validate a child."""
    validated = defaultdict(list)
    pres = gateway.const.Presentation
    set_req = gateway.const.SetReq
    child_type_name = next(
        (member.name for member in pres if member.value == child.type), None)
    value_types = [value_type] if value_type else [*child.values]
    value_type_names = [
        member.name for member in set_req if member.value in value_types]
    platforms = TYPE_TO_PLATFORMS.get(child_type_name, [])
    if not platforms:
        _LOGGER.warning("Child type %s is not supported", child.type)
        return validated

    for platform in platforms:
        v_names = FLAT_PLATFORM_TYPES[platform, child_type_name]
        if not isinstance(v_names, list):
            v_names = [v_names]
        v_names = [v_name for v_name in v_names if v_name in value_type_names]

        for v_name in v_names:
            child_schema_gen = SCHEMAS.get((platform, v_name), default_schema)
            child_schema = child_schema_gen(gateway, child, v_name)
            try:
                child_schema(child.values)
            except vol.Invalid as exc:
                _LOGGER.warning(
                    "Invalid %s on node %s, %s platform: %s",
                    child, node_id, platform, exc)
                continue
            dev_id = id(gateway), node_id, child.id, set_req[v_name].value
            validated[platform].append(dev_id)

    return validated
