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


def validate_child(gateway, node_id, child):
    """Validate that a child has the correct values according to schema.

    Return a dict of platform with a list of device ids for validated devices.
    """
    validated = defaultdict(list)

    if not child.values:
        _LOGGER.debug(
            "No child values for node %s child %s", node_id, child.id)
        return validated
    if gateway.sensors[node_id].sketch_name is None:
        _LOGGER.debug("Node %s is missing sketch name", node_id)
        return validated
    pres = gateway.const.Presentation
    set_req = gateway.const.SetReq
    s_name = next(
        (member.name for member in pres if member.value == child.type), None)
    if s_name not in MYSENSORS_CONST_SCHEMA:
        _LOGGER.warning("Child type %s is not supported", s_name)
        return validated
    child_schemas = MYSENSORS_CONST_SCHEMA[s_name]

    def msg(name):
        """Return a message for an invalid schema."""
        return "{} requires value_type {}".format(
            pres(child.type).name, set_req[name].name)

    for schema in child_schemas:
        platform = schema[PLATFORM]
        v_name = schema[TYPE]
        value_type = next(
            (member.value for member in set_req if member.name == v_name),
            None)
        if value_type is None:
            continue
        _child_schema = child.get_schema(gateway.protocol_version)
        vol_schema = _child_schema.extend(
            {vol.Required(set_req[key].value, msg=msg(key)):
             _child_schema.schema.get(set_req[key].value, val)
             for key, val in schema.get(SCHEMA, {v_name: cv.string}).items()},
            extra=vol.ALLOW_EXTRA)
        try:
            vol_schema(child.values)
        except vol.Invalid as exc:
            level = (logging.WARNING if value_type in child.values
                     else logging.DEBUG)
            _LOGGER.log(
                level,
                "Invalid values: %s: %s platform: node %s child %s: %s",
                child.values, platform, node_id, child.id, exc)
            continue
        dev_id = id(gateway), node_id, child.id, value_type
        validated[platform].append(dev_id)
    return validated
