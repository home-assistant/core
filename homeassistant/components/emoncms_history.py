"""
A component which allows you to send data to Emoncms.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/emoncms_history/
"""
import logging
import json

import voluptuous as vol
import requests

from homeassistant.const import (
    CONF_API_KEY, CONF_WHITELIST,
    CONF_URL, STATE_UNKNOWN,
    STATE_UNAVAILABLE)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import state as state_helper
from homeassistant.helpers.event import track_state_change

_LOGGER = logging.getLogger(__name__)

DOMAIN = "emoncms_history"
CONF_INPUTNODE = "inputnode"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_INPUTNODE): cv.positive_int,
        vol.Required(CONF_WHITELIST): cv.entity_ids,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the emoncms_history component."""
    conf = config[DOMAIN]
    whitelist = conf.get(CONF_WHITELIST)
    # defined here so that previous values that did not change
    # are send as well, otherwise emoncms will list the inputs
    # as inactive and possibly send emails that feeds based
    # on the input value have not changed (if the user enabled
    # that with the extra, optional scripts)
    json_body = {}

    def _state_changed(entity_id, old_state, new_state):
        """Send new states to emoncms."""
        if new_state is None or new_state in (STATE_UNKNOWN, "",
                                              STATE_UNAVAILABLE):
            return

        try:
            _state = state_helper.state_as_number(new_state)
        except ValueError:
            return

        json_body[entity_id] = _state
        json_str = json.dumps(json_body, separators=(",", ":"))
        json_str = json_str.replace("\"", "")
        json_str = json_str.replace("{", "").replace("}", "")
        json_str = "{{{}}}".format(json_str)

        send_data(conf.get(CONF_URL), conf.get(CONF_API_KEY),
                  str(conf.get(CONF_INPUTNODE)), json_str)

    track_state_change(hass, whitelist, _state_changed)

    return True


def send_data(url, apikey, node, jsonstr):
    """Send the collected data to emoncms."""
    try:
        fullurl = "{}/input/post.json".format(url)
        req = requests.get(fullurl, params={"apikey": apikey,
                                            "node": node,
                                            "json": jsonstr},
                           allow_redirects=True, timeout=5)

    except requests.exceptions.RequestException:
        _LOGGER.error("Error saving data '%s' to '%s'", json, fullurl)

    else:
        if req.status_code != 200:
            _LOGGER.error("Error saving data '%s' to '%s'" +
                          "(http status code = %d)", json, fullurl,
                          req.status_code)
