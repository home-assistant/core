"""Config flow to configure the Event Hub integration."""
import logging

import voluptuous as vol
from azure.eventhub import EventData, EventHubClientAsync

from homeassistant import config_entries
from homeassistant.core import Event, HomeAssistant
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.json import JSONEncoder
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from homeassistant.components.azure_event_hub import DOMAIN, CONFIG_SCHEMA, CONF_EVENT_HUB_NAMESPACE, CONF_EVENT_HUB_INSTANCE_NAME, CONF_EVENT_HUB_SAS_POLICY, CONF_EVENT_HUB_SAS_KEY, CONF_EVENT_HUB_CON_STRING, CONF_IOT_HUB_CON_STRING, CONF_FILTER

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class EventHubFlowHandler(ConfigFlow):
    """Handle a Event Hub config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    _hassio_discovery = None

    def __init__(self):
        """Initialize Event Hub flow."""
        pass

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return await self._show_setup_form(user_input)

        errors = {}

        entities_filter = user_input[CONF_FILTER]
        if user_input[CONF_IOT_HUB_CON_STRING]:
            client = EventHubClientAsync.from_iot_connection_string(
                user_input[CONF_IOT_HUB_CON_STRING]
            )
        elif user_input[CONF_EVENT_HUB_CON_STRING]:
            client = EventHubClientAsync.from_connection_string(
                user_input[CONF_EVENT_HUB_CON_STRING]
            )
        else:
            event_hub_address = "amqps://{}.servicebus.windows.net/{}".format(
                user_input[CONF_EVENT_HUB_NAMESPACE], user_input[CONF_EVENT_HUB_INSTANCE_NAME]
            )
            client = EventHubClientAsync(
                event_hub_address,
                username=user_input[CONF_EVENT_HUB_SAS_POLICY],
                password=user_input[CONF_EVENT_HUB_SAS_KEY],
            )
    
        async_sender = client.add_async_sender()
        await client.run_async()

        # encoder = JSONEncoder()
    
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
                json.dumps(obj=state, cls=JSONEncoder).encode("utf-8")
                # json.dumps(obj=state.as_dict(), default=encoder.default).encode("utf-8")
            )
            try:
                await async_sender.send(event_data)
            except AttributeError:
                await async_sender.reconnect_async()
                await async_sender.send(event_data)
    
        async def async_shutdown(event: Event):
            """Shut down the client."""
            await client.stop_async()
    
        hass.bus.async_listen(EVENT_STATE_CHANGED, async_send_to_event_hub)
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown)
    
        return True
    
