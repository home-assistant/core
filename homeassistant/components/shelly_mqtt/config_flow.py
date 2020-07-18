"""Config flow for Shelly MQTT integration."""
import asyncio
import json
import logging
from pprint import pformat

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_DEVICE_ID

from .const import (
    ANNOUNCE_COMMAND,
    COMMAND_SUFFIX,
    COMMON_ANNOUNCE_TOPIC,
    COMMON_COMMAND_TOPIC,
    CONF_ID,
    CONF_MODEL,
    CONF_TOPIC,
    MODEL_TITLE,
    MODELS,
    ONLINE_SUFFIX,
    UPDATE_COMMAND,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5


async def validate_input(hass: core.HomeAssistant, data, timeout=DEFAULT_TIMEOUT):
    """Validate the user input is a real device."""
    topic = data[CONF_TOPIC]
    mqtt = hass.components.mqtt

    future = asyncio.Future()

    def message_received(msg):
        if not future.done():
            future.set_result(True)

    unsubscribe = await mqtt.async_subscribe(topic + ONLINE_SUFFIX, message_received)
    mqtt.async_publish(topic + COMMAND_SUFFIX, UPDATE_COMMAND)

    # give device time to respond
    try:
        await asyncio.wait_for(future, timeout)
        return future.done()
    except asyncio.TimeoutError:
        return False
    finally:
        unsubscribe()


async def async_discovery(hass, timeout=DEFAULT_TIMEOUT):
    """Return Shelly MQTT devices connected to the MQTT broker."""
    _LOGGER.debug("Starting Shelly MQTT discovery...")
    mqtt = hass.components.mqtt

    devices = []

    def message_received(msg):
        devices.append(json.loads(msg.payload))

    unsubscribe = await mqtt.async_subscribe(COMMON_ANNOUNCE_TOPIC, message_received)
    mqtt.async_publish(COMMON_COMMAND_TOPIC, ANNOUNCE_COMMAND)
    # give all devices time to announce themselves
    await asyncio.sleep(timeout)
    unsubscribe()

    return devices


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shelly MQTT."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Shelly MQTT config flow."""
        self._device = None
        self._devices = []

    async def async_step_user(self, user_input=None):
        """Handle user flow."""
        if "mqtt" not in self.hass.config.components:
            return self.async_abort(reason="mqtt_required")

        if user_input is not None:
            return await self.async_step_device()

        return self.async_show_form(step_id="user")

    async def async_step_device(self, user_input=None):
        """Let the user pick the device."""
        if user_input:
            for device in self._devices:
                if device[CONF_ID] == user_input[CONF_DEVICE_ID]:
                    self._device = device[CONF_ID]
                    await self.async_set_unique_id(self._device)
                    self._abort_if_unique_id_configured()
                    return await self.async_step_topic()

        discovery = await async_discovery(self.hass)
        for device in discovery:
            configured = any(
                entry.unique_id == device[CONF_ID]
                for entry in self._async_current_entries()
            )

            model = device[CONF_ID].split("-")[0]
            supported = MODELS.get(model)

            if supported and not configured:
                self._devices.append(device)

        _LOGGER.debug("Discovered Shelly MQTT devices %s", pformat(self._devices))

        if self._devices:
            names = [device[CONF_ID] for device in self._devices]

            return self.async_show_form(
                step_id="device",
                data_schema=vol.Schema({vol.Required(CONF_DEVICE_ID): vol.In(names)}),
            )

        return self.async_abort(reason="no_devices_found")

    async def async_step_topic(self, user_input=None):
        """Model and topic configuration for Shelly MQTT device."""
        errors = {}
        if user_input:
            try:
                self.hass.components.mqtt.valid_publish_topic(user_input[CONF_TOPIC])
                success = await validate_input(self.hass, user_input)
                if success:
                    device_id = self._device
                    model = device_id.split("-")[0]
                    title = f"{MODELS[model][MODEL_TITLE]} ({device_id})"
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_DEVICE_ID: device_id,
                            CONF_MODEL: model,
                            CONF_TOPIC: user_input[CONF_TOPIC],
                        },
                    )

                errors["base"] = "cannot_connect"
                topic = user_input[CONF_TOPIC]
            except vol.Invalid:
                errors["base"] = "invalid_topic"
                topic = user_input[CONF_TOPIC]
        else:
            topic = f"shellies/{self._device}/"

        return self.async_show_form(
            step_id="topic",
            data_schema=vol.Schema({vol.Required(CONF_TOPIC, default=topic): str}),
            errors=errors,
        )
