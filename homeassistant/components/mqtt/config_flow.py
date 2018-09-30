"""Config flow for MQTT."""
from collections import OrderedDict
import queue

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from .const import CONF_BROKER, CONF_DISCOVERY, DEFAULT_DISCOVERY


@config_entries.HANDLERS.register('mqtt')
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')

        return await self.async_step_broker()

    async def async_step_broker(self, user_input=None):
        """Confirm the setup."""
        errors = {}

        if user_input is not None:
            can_connect = await self.hass.async_add_executor_job(
                try_connection, user_input[CONF_BROKER], user_input[CONF_PORT],
                user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD))

            if can_connect:
                return self.async_create_entry(
                    title=user_input[CONF_BROKER], data=user_input)

            errors['base'] = 'cannot_connect'

        fields = OrderedDict()
        fields[vol.Required(CONF_BROKER)] = str
        fields[vol.Required(CONF_PORT, default=1883)] = vol.Coerce(int)
        fields[vol.Optional(CONF_USERNAME)] = str
        fields[vol.Optional(CONF_PASSWORD)] = str
        fields[vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY)] = bool

        return self.async_show_form(
            step_id='broker', data_schema=vol.Schema(fields), errors=errors)

    async def async_step_import(self, user_input):
        """Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')

        return self.async_create_entry(title='configuration.yaml', data={})


def try_connection(broker, port, username, password):
    """Test if we can connect to an MQTT broker."""
    import paho.mqtt.client as mqtt
    client = mqtt.Client()
    if username and password:
        client.username_pw_set(username, password)

    result = queue.Queue(maxsize=1)

    def on_connect(client_, userdata, flags, result_code):
        """Handle connection result."""
        result.put(result_code == mqtt.CONNACK_ACCEPTED)

    client.on_connect = on_connect

    client.connect_async(broker, port)
    client.loop_start()

    try:
        return result.get(timeout=5)
    except queue.Empty:
        return False
    finally:
        client.disconnect()
        client.loop_stop()
