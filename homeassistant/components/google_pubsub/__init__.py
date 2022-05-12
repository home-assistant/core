"""Support for Google Cloud Pub/Sub."""
from __future__ import annotations

import datetime
import json
import logging
import os

from google.cloud.pubsub_v1 import PublisherClient
import voluptuous as vol

from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "google_pubsub"

CONF_PROJECT_ID = "project_id"
CONF_TOPIC_NAME = "topic_name"
CONF_SERVICE_PRINCIPAL = "credentials_json"
CONF_FILTER = "filter"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PROJECT_ID): cv.string,
                vol.Required(CONF_TOPIC_NAME): cv.string,
                vol.Required(CONF_SERVICE_PRINCIPAL): cv.string,
                vol.Required(CONF_FILTER): FILTER_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate Google Pub/Sub component."""
    config = yaml_config[DOMAIN]
    project_id = config[CONF_PROJECT_ID]
    topic_name = config[CONF_TOPIC_NAME]
    service_principal_path = hass.config.path(config[CONF_SERVICE_PRINCIPAL])

    if not os.path.isfile(service_principal_path):
        _LOGGER.error("Path to credentials file cannot be found")
        return False

    entities_filter = config[CONF_FILTER]

    publisher = PublisherClient.from_service_account_json(service_principal_path)

    topic_path = publisher.topic_path(project_id, topic_name)

    encoder = DateTimeJSONEncoder()

    def send_to_pubsub(event: Event):
        """Send states to Pub/Sub."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not entities_filter(state.entity_id)
        ):
            return

        as_dict = state.as_dict()
        data = json.dumps(obj=as_dict, default=encoder.encode).encode("utf-8")

        publisher.publish(topic_path, data=data)

    hass.bus.listen(EVENT_STATE_CHANGED, send_to_pubsub)

    return True


class DateTimeJSONEncoder(json.JSONEncoder):
    """Encode python objects.

    Additionally add encoding for datetime objects as isoformat.
    """

    def default(self, o):
        """Implement encoding logic."""
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)
