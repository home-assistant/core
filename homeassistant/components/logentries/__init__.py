"""Support for sending data to Logentries webhook endpoint."""

import json
import logging

import requests
import voluptuous as vol

from homeassistant.const import CONF_TOKEN, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, state as state_helper
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "logentries"

DEFAULT_HOST = "https://webhook.logentries.com/noformat/logs/"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_TOKEN): cv.string})}, extra=vol.ALLOW_EXTRA
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Logentries component."""
    conf = config[DOMAIN]
    token = conf.get(CONF_TOKEN)
    le_wh = f"{DEFAULT_HOST}{token}"

    def logentries_event_listener(event):
        """Listen for new messages on the bus and sends them to Logentries."""
        if (state := event.data.get("new_state")) is None:
            return
        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state
        json_body = [
            {
                "domain": state.domain,
                "entity_id": state.object_id,
                "attributes": dict(state.attributes),
                "time": str(event.time_fired),
                "value": _state,
            }
        ]
        try:
            payload = {"host": le_wh, "event": json_body}
            requests.post(le_wh, data=json.dumps(payload), timeout=10)
        except requests.exceptions.RequestException:
            _LOGGER.exception("Error sending to Logentries")

    hass.bus.listen(EVENT_STATE_CHANGED, logentries_event_listener)

    return True
