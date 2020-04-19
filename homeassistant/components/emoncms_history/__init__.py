"""Support for sending data to Emoncms."""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_WHITELIST,
    HTTP_OK,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_time
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "emoncms_history"
CONF_INPUTNODE = "inputnode"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_URL): cv.string,
                vol.Required(CONF_INPUTNODE): cv.positive_int,
                vol.Required(CONF_WHITELIST): cv.entity_ids,
                vol.Optional(CONF_SCAN_INTERVAL, default=30): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Emoncms history component."""
    conf = config[DOMAIN]
    whitelist = conf.get(CONF_WHITELIST)

    def send_data(url, apikey, node, payload):
        """Send payload data to Emoncms."""
        try:
            fullurl = f"{url}/input/post.json"
            data = {"apikey": apikey, "data": payload}
            parameters = {"node": node}
            req = requests.post(
                fullurl, params=parameters, data=data, allow_redirects=True, timeout=5
            )

        except requests.exceptions.RequestException:
            _LOGGER.error("Error saving data '%s' to '%s'", payload, fullurl)

        else:
            if req.status_code != HTTP_OK:
                _LOGGER.error(
                    "Error saving data %s to %s (http status code = %d)",
                    payload,
                    fullurl,
                    req.status_code,
                )

    def update_emoncms(time):
        """Send whitelisted entities states regularly to Emoncms."""
        payload_dict = {}

        for entity_id in whitelist:
            state = hass.states.get(entity_id)

            if state is None or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE):
                continue

            try:
                payload_dict[entity_id] = state_helper.state_as_number(state)
            except ValueError:
                continue

        if payload_dict:
            payload = "{%s}" % ",".join(
                f"{key}:{val}" for key, val in payload_dict.items()
            )

            send_data(
                conf.get(CONF_URL),
                conf.get(CONF_API_KEY),
                str(conf.get(CONF_INPUTNODE)),
                payload,
            )

        track_point_in_time(
            hass, update_emoncms, time + timedelta(seconds=conf.get(CONF_SCAN_INTERVAL))
        )

    update_emoncms(dt_util.utcnow())
    return True
