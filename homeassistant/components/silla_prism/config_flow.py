"""Config flow for the Silla Prism integration."""

import asyncio
from typing import Any, override

from pysillaprism import parse_hello, parse_message
from pysillaprism.exceptions import PrismParseError
import voluptuous as vol

from homeassistant.components.mqtt import (
    ReceiveMessage,
    async_wait_for_mqtt_client,
    client as mqtt,
    valid_publish_topic,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC, DOMAIN

#: How long to wait for a retained status message when validating a base topic.
_PROBE_TIMEOUT = 5


class PrismConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Silla Prism config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._base_topic: str = DEFAULT_BASE_TOPIC
        self._serial: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow started by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            base_topic = user_input[CONF_BASE_TOPIC].strip().strip("/")
            try:
                valid_publish_topic(base_topic)
            except vol.Invalid:
                errors[CONF_BASE_TOPIC] = "invalid_base_topic"
            else:
                await self.async_set_unique_id(base_topic)
                self._abort_if_unique_id_configured()

                if not await async_wait_for_mqtt_client(self.hass):
                    errors["base"] = "mqtt_unavailable"
                elif not await self._async_probe(base_topic):
                    errors["base"] = "no_device"
                else:
                    return self.async_create_entry(
                        title="Silla Prism", data={CONF_BASE_TOPIC: base_topic}
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_TOPIC, default=DEFAULT_BASE_TOPIC): str,
                }
            ),
            errors=errors,
        )

    async def _async_probe(self, base_topic: str) -> bool:
        """Return True if a recognizable Prism message is seen under ``base_topic``."""
        seen = asyncio.Event()

        @callback
        def _message(msg: ReceiveMessage) -> None:
            if isinstance(msg.payload, str) and (
                parse_message(base_topic, msg.topic, msg.payload) is not None
            ):
                seen.set()

        unsubscribe = await mqtt.async_subscribe(self.hass, f"{base_topic}/#", _message)
        try:
            async with asyncio.timeout(_PROBE_TIMEOUT):
                await seen.wait()
        except TimeoutError:
            return False
        finally:
            unsubscribe()
        return True

    @override
    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via the Prism ``hello`` topic."""
        payload = discovery_info.payload
        if not payload or not isinstance(payload, str):
            return self.async_abort(reason="invalid_discovery_info")

        # Discovery is registered on "<base_topic>/hello".
        self._base_topic = discovery_info.topic.removesuffix("/hello")
        if self._base_topic == discovery_info.topic:
            return self.async_abort(reason="invalid_discovery_info")

        try:
            self._serial = parse_hello(payload).serial
        except PrismParseError:
            return self.async_abort(reason="invalid_discovery_info")

        await self.async_set_unique_id(self._base_topic)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"serial": self._serial}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered Prism."""
        if user_input is not None:
            return self.async_create_entry(
                title="Silla Prism", data={CONF_BASE_TOPIC: self._base_topic}
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"serial": self._serial or ""},
        )
