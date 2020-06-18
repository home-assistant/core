"""Config flow for MQTT."""
from collections import OrderedDict
import queue

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)

from .const import CONF_BROKER, CONF_DISCOVERY, DEFAULT_DISCOVERY


@config_entries.HANDLERS.register("mqtt")
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    _hassio_discovery = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_broker()

    async def async_step_broker(self, user_input=None):
        """Confirm the setup."""
        errors = {}

        if user_input is not None:
            can_connect = await self.hass.async_add_executor_job(
                try_connection,
                user_input[CONF_BROKER],
                user_input[CONF_PORT],
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
            )

            if can_connect:
                return self.async_create_entry(
                    title=user_input[CONF_BROKER], data=user_input
                )

            errors["base"] = "cannot_connect"

        fields = OrderedDict()
        fields[vol.Required(CONF_BROKER)] = str
        fields[vol.Required(CONF_PORT, default=1883)] = vol.Coerce(int)
        fields[vol.Optional(CONF_USERNAME)] = str
        fields[vol.Optional(CONF_PASSWORD)] = str
        fields[vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY)] = bool

        return self.async_show_form(
            step_id="broker", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_import(self, user_input):
        """Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="configuration.yaml", data={})

    async def async_step_hassio(self, discovery_info):
        """Receive a Hass.io discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self._hassio_discovery = discovery_info

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input=None):
        """Confirm a Hass.io discovery."""
        errors = {}

        if user_input is not None:
            data = self._hassio_discovery
            can_connect = await self.hass.async_add_executor_job(
                try_connection,
                data[CONF_HOST],
                data[CONF_PORT],
                data.get(CONF_USERNAME),
                data.get(CONF_PASSWORD),
                data.get(CONF_PROTOCOL),
            )

            if can_connect:
                return self.async_create_entry(
                    title=data["addon"],
                    data={
                        CONF_BROKER: data[CONF_HOST],
                        CONF_PORT: data[CONF_PORT],
                        CONF_USERNAME: data.get(CONF_USERNAME),
                        CONF_PASSWORD: data.get(CONF_PASSWORD),
                        CONF_PROTOCOL: data.get(CONF_PROTOCOL),
                        CONF_DISCOVERY: user_input[CONF_DISCOVERY],
                    },
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            data_schema=vol.Schema(
                {vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): bool}
            ),
            errors=errors,
        )


def try_connection(broker, port, username, password, protocol="3.1"):
    """Test if we can connect to an MQTT broker."""
    # pylint: disable=import-outside-toplevel
    import paho.mqtt.client as mqtt

    if protocol == "3.1":
        proto = mqtt.MQTTv31
    else:
        proto = mqtt.MQTTv311

    client = mqtt.Client(protocol=proto)
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
