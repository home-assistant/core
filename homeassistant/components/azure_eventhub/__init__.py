"""Support for Azure Event Hubs."""
import datetime
import json
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant.const import (
    EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'azure_eventhub'

CONF_EVENT_HUB_ADDRESS = 'event_hub_address'
CONF_EVENT_HUB_SAS_POLICY = 'event_hub_sas_policy'
CONF_EVENT_HUB_SAS_KEY = 'event_hub_sas_key'
CONF_FILTER = 'filter'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EVENT_HUB_ADDRESS): cv.string,
        vol.Required(CONF_EVENT_HUB_SAS_POLICY): cv.string,
        vol.Required(CONF_EVENT_HUB_SAS_KEY): cv.string,
        vol.Required(CONF_FILTER): FILTER_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Azure EH component."""
    from azure.eventhub import EventData, EventHubClientAsync, AsyncSender

    config = yaml_config[DOMAIN]
    event_hub_address = config[CONF_EVENT_HUB_ADDRESS]
    event_hub_sas_policy = config[CONF_EVENT_HUB_SAS_POLICY]
    event_hub_sas_key = config[CONF_EVENT_HUB_SAS_KEY]

    entities_filter = config[CONF_FILTER]

    client = EventHubClientAsync(
        event_hub_address,
        debug=True,
        username=event_hub_sas_policy,
        password=event_hub_sas_key)

    sender = client.add_async_sender()
    client.run_async()

    encoder = DateTimeJSONEncoder()

    async def send_to_eventhub(event: Event):
        """Send states to Pub/Sub."""
        state = event.data.get('new_state')
        if (state is None
                or state.state in (STATE_UNKNOWN, '', STATE_UNAVAILABLE)
                or not entities_filter(state.entity_id)):
            return

        event_data = EventData(
            json.dumps(
                obj=state.as_dict(),
                default=encoder.encode
            ).encode('utf-8')
        )

        await sender.send(event_data)

    hass.bus.listen(EVENT_STATE_CHANGED, send_to_eventhub)
    return True


class DateTimeJSONEncoder(json.JSONEncoder):
    """Encode python objects.

    Additionally add encoding for datetime objects as isoformat.
    """

    def default(self, o):  # pylint: disable=E0202
        """Implement encoding logic."""
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)
