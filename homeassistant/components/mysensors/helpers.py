"""Helper functions for mysensors package."""
from collections import defaultdict
import logging

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_DEVICES, DOMAIN, MYSENSORS_CONST_SCHEMA, PLATFORM, SCHEMA, TYPE)

_LOGGER = logging.getLogger(__name__)


@callback
def discover_mysensors_platform(hass, hass_config, platform, new_devices):
    """Discover a MySensors platform."""
    task = hass.async_create_task(discovery.async_load_platform(
        hass, platform, DOMAIN,
        {ATTR_DEVICES: new_devices, CONF_NAME: DOMAIN}, hass_config))
    return task


def validate_set(msg):
    """Validate a set message."""
    child = msg.gateway.sensors[msg.node_id].children[msg.child_id]
    return validate_child(msg.gateway, msg.node_id, child, msg.sub_type)


def validate_child(gateway, node_id, child, value_type=None):
    """Validate a child."""
    validated = defaultdict(list)
    if gateway.sensors[node_id].sketch_name is None:
        _LOGGER.debug("Node %s is missing sketch name", node_id)
        return validated
    pres = gateway.const.Presentation
    set_req = gateway.const.SetReq
    s_name = next(
        (member.name for member in pres if member.value == child.type), None)
    child_schemas = MYSENSORS_CONST_SCHEMA.get(s_name, [])
    if not child_schemas:
        _LOGGER.warning("Child type %s is not supported", s_name)

    def invalid_msg(name):
        """Return a message for an invalid schema."""
        return "{} requires value_type {}".format(
            pres(child.type).name, set_req[name].name)

    for schema in child_schemas:
        platform = schema[PLATFORM]
        v_name = schema[TYPE]
        _child_schema = child.get_schema(gateway.protocol_version)
        vol_schema = _child_schema.extend(
            {vol.Required(set_req[key].value, msg=invalid_msg(key)):
             _child_schema.schema.get(set_req[key].value, val)
             for key, val in schema.get(SCHEMA, {v_name: cv.string}).items()},
            extra=vol.ALLOW_EXTRA)
        if (value_type and value_type not in vol_schema.schema
                or not any(
                    child_value_type in vol_schema.schema
                    for child_value_type in child.values)):
            continue
        try:
            vol_schema(child.values)
        except vol.Invalid as exc:
            _LOGGER.warning(
                "Invalid values: %s: %s platform: node %s child %s: %s",
                child.values, platform, node_id, child.id, exc)
            continue
        dev_id = id(gateway), node_id, child.id, set_req[v_name].value
        validated[platform].append(dev_id)
    return validated
