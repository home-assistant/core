"""
Core support for mapping a subset of values in a JSON dictionary
into component attributes.
"""

import json
import logging

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_JSON_ATTRS = 'json_attributes'

json_attrs_validation = cv.ensure_list_csv


def extract_json_attrs(json_attrs_conf, value):
    _LOGGER.debug("extract_json_attrs called with value %s and conf %s",
                  value, json_attrs_conf)
    attributes = {}
    if value:
        try:
            json_dict = json.loads(value)
            if isinstance(json_dict, dict):
                attributes = {k: json_dict[k]
                              for k in json_attrs_conf
                              if k in json_dict}
            else:
                _LOGGER.warning("JSON result was not a dictionary")
        except ValueError:
            _LOGGER.warning("REST result could not be parsed as JSON")
            _LOGGER.debug("Erroneous JSON: %s", value)
    else:
        _LOGGER.warning("Empty reply found when expecting JSON data")
    return attributes
