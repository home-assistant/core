"""Support for Azure Event Hubs."""
import json
import logging
from typing import Any, Dict

from azure.eventhub import EventData, EventHubClientAsync
import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.json import JSONEncoder

_LOGGER = logging.getLogger(__name__)

DOMAIN = "azure_event_hub"

CONF_EVENT_HUB_NAMESPACE = "event_hub_namespace"
CONF_EVENT_HUB_INSTANCE_NAME = "event_hub_instance_name"
CONF_EVENT_HUB_SAS_POLICY = "event_hub_sas_policy"
CONF_EVENT_HUB_SAS_KEY = "event_hub_sas_key"
CONF_EVENT_HUB_CON_STRING = "event_hub_connection_string"
CONF_IOT_HUB_CON_STRING = "iot_hub_connection_string"
CONF_FILTER = "filter"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            vol.Schema(
                {
                    vol.Required(CONF_IOT_HUB_CON_STRING): cv.string,
                    vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
                }
            ),
            vol.Schema(
                {
                    vol.Required(CONF_EVENT_HUB_CON_STRING): cv.string,
                    vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
                }
            ),
            vol.Schema(
                {
                    vol.Required(CONF_EVENT_HUB_NAMESPACE): cv.string,
                    vol.Required(CONF_EVENT_HUB_INSTANCE_NAME): cv.string,
                    vol.Required(CONF_EVENT_HUB_SAS_POLICY): cv.string,
                    vol.Required(CONF_EVENT_HUB_SAS_KEY): cv.string,
                    vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, yaml_config):
    """Activate Azure EH component."""
    config = yaml_config[DOMAIN]
    _LOGGER.debug("Config: %s", config)
    entities_filter = config.get(CONF_FILTER)
    if config.get(CONF_EVENT_HUB_CON_STRING, None):
        client_args = {"conn_str": config[CONF_EVENT_HUB_CON_STRING]}
        conn_str_client = True
    else:
        client_args = {
            "fully_qualified_namespace": f"{config[CONF_EVENT_HUB_NAMESPACE]}.servicebus.windows.net",
            "credential": EventHubSharedKeyCredential(
                policy=config[CONF_EVENT_HUB_SAS_POLICY],
                key=config[CONF_EVENT_HUB_SAS_KEY],
            ),
            "eventhub_name": config[CONF_EVENT_HUB_INSTANCE_NAME],
        }
        conn_str_client = False

    instance = hass.data[DOMAIN] = AEHThread(
        hass, client_args, conn_str_client, entities_filter
    )
    instance.async_initialize()
    instance.start()

    return await instance.async_ready

    entities_filter = config[CONF_FILTER]
    if config[CONF_IOT_HUB_CON_STRING]:
        client = EventHubClientAsync.from_iot_connection_string(
            config[CONF_IOT_HUB_CON_STRING]
        )
    elif config[CONF_EVENT_HUB_CON_STRING]:
        client = EventHubClientAsync.from_connection_string(
            config[CONF_EVENT_HUB_CON_STRING]
        )
    else:
        event_hub_address = "amqps://{}.servicebus.windows.net/{}".format(
            config[CONF_EVENT_HUB_NAMESPACE], config[CONF_EVENT_HUB_INSTANCE_NAME]
        )
        client = EventHubClientAsync(
            event_hub_address,
            username=config[CONF_EVENT_HUB_SAS_POLICY],
            password=config[CONF_EVENT_HUB_SAS_KEY],
        )

    async_sender = client.add_async_sender()
    await client.run_async()

    encoder = JSONEncoder()

    async def async_send_to_event_hub(event: Event):
        """Send states to Event Hub."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not entities_filter(state.entity_id)
        ):
            return

        event_data = EventData(
            json.dumps(obj=state.as_dict(), default=encoder.encode).encode("utf-8")
        )
        await async_sender.send(event_data)

    async def async_shutdown(event: Event):
        """Shut down the client."""
        await client.stop_async()

    hass.bus.async_listen(EVENT_STATE_CHANGED, async_send_to_event_hub)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown)

    return True
