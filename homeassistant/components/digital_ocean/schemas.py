"""Holds validation schemas used across the integration."""
import ipaddress

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from . import constants as const

UPDATE_DOMAIN_RECORD_SCHEMA = vol.Schema(
    {
        vol.Required(const.ATTR_DOMAIN_NAME): cv.matches_regex(
            const.DOMAIN_NAME_REGEX,
        ),
        vol.Required(const.ATTR_RECORD_NAME): str,
        vol.Required(const.ATTR_RECORD_VALUE): vol.Any(
            ipaddress.ip_address,
            cv.matches_regex(const.DOMAIN_NAME_REGEX),
            msg="value must be either an IPV4 address or another domain name",
        ),
        vol.Required(const.ATTR_RECORD_TYPE): vol.In(
            container=("A", "CNAME"), msg="Invalid record type. Use either A or CNAME "
        ),
    }
)
