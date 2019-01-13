import datetime
import json
import logging
import os
from typing import Dict, Any

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    EVENT_STATE_CHANGED, STATE_UNKNOWN, STATE_UNAVAILABLE)
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.helpers.entityfilter import FILTER_SCHEMA

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['google-cloud-pubsub==0.39.1']

DOMAIN = 'google_pubsub'

CONF_PROJECT_ID = 'project_id'
CONF_TOPIC_NAME = 'topic_name'
CONF_SERVICE_PRINCIPAL = 'credentials_json'
CONF_FILTER = 'filter'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PROJECT_ID): cv.string,
        vol.Required(CONF_TOPIC_NAME): cv.string,
        vol.Required(CONF_SERVICE_PRINCIPAL): cv.string,
        vol.Required(CONF_FILTER): FILTER_SCHEMA
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    from google.cloud import pubsub_v1

    config = yaml_config.get(DOMAIN, {})
    project_id = config[CONF_PROJECT_ID]
    topic_name = config[CONF_TOPIC_NAME]
    service_principal_path = os.path.join(hass.config.config_dir,
                                          config[CONF_SERVICE_PRINCIPAL])

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = service_principal_path

    entities_filter = config[CONF_FILTER]

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)

    encoder = DateTimeJSONEncoder()

    def send_to_pubsub(event: Event):
        state = event.data.get('new_state')
        if (state is None
                or state.state in (STATE_UNKNOWN, '', STATE_UNAVAILABLE)
                or not entities_filter(state.entity_id)):
            return

        as_dict = state.as_dict()
        data = json.dumps(
            obj=as_dict,
            default=encoder.encode
        ).encode('utf-8')

        publisher.publish(topic_path, data=data)

    hass.bus.listen(EVENT_STATE_CHANGED, send_to_pubsub)

    return True


class DateTimeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        else:
            return super(DateTimeJSONEncoder, self).default(obj)
