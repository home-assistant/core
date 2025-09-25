"""Config flow for Greencell EVSE integration in Home Assistant.

This module implements:
- EVSEConfigFlow: an asyncio-based MQTT discovery flow that:
  * Subscribes to the GREENCELL_DISC_TOPIC to listen for device response messages.
  * Publishes a BROADCAST discovery request to GREENCELL_BROADCAST_TOPIC.
  * Waits up to DISCOVERY_TIMEOUT seconds for a response, then aborts or continues.
  * Extracts the device serial number from the discovery payload.
  * Determines the device model name (Habu Den or Other) from the serial prefix.
  * Registers a unique ID and creates the config entry with the serial_number.
"""

import asyncio
import json
import logging
from typing import Any

from greencell_client.utils import GreencellUtils
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DISCOVERY_TIMEOUT,
    DOMAIN,
    GREENCELL_BROADCAST_TOPIC,
    GREENCELL_DISC_TOPIC,
    GREENCELL_HABU_DEN,
    GREENCELL_OTHER_DEVICE,
)

_LOGGER = logging.getLogger(__name__)


class EVSEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Greencell EVSE devices."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: dict[str, dict[str, Any]] = {}

    def _get_device_name(self, serial: str) -> str:
        """Determine the device name based on the serial number."""
        return (
            GREENCELL_HABU_DEN
            if GreencellUtils.device_is_habu_den(serial)
            else GREENCELL_OTHER_DEVICE
        )

    async def _publish_disc_request(self) -> None:
        """Publish a discovery request to the GREENCELL_BROADCAST_TOPIC."""
        payload = json.dumps({"name": "BROADCAST"})
        await mqtt.async_publish(
            self.hass, GREENCELL_BROADCAST_TOPIC, payload, qos=0, retain=True
        )

    @callback
    def _mqtt_message_received(self, msg) -> None:
        """Handle incoming MQTT messages on the discovery topic."""
        try:
            payload = json.loads(msg.payload)
            serial = payload.get("id")
            if isinstance(serial, str) and serial.strip():
                self._discovered[serial] = payload
        except json.JSONDecodeError:
            _LOGGER.debug("Invalid JSON in discovery payload: %s", msg.payload)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initial step: broadcast discovery and collect responses."""

        try:
            remove_listener = await mqtt.async_subscribe(
                self.hass, GREENCELL_DISC_TOPIC, self._mqtt_message_received
            )
        except HomeAssistantError as err:
            _LOGGER.error("Failed to subscribe to discovery topic: %s", err)
            return self.async_abort(reason="mqtt_subscription_failed")

        try:
            await self._publish_disc_request()
            await asyncio.sleep(DISCOVERY_TIMEOUT)
        finally:
            remove_listener()

        if not self._discovered:
            return self.async_abort(reason="no_discovery_data")

        if len(self._discovered) == 1:
            serial = next(iter(self._discovered))
            return await self._create_entry(serial)

        return await self.async_step_select()

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Second step: let the user select one of the discovered devices."""

        if user_input is not None:
            serial = user_input["serial_number"]
            return await self._create_entry(serial)

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {vol.Required("serial_number"): vol.In(list(self._discovered.keys()))}
            ),
            description_placeholders={"count": str(len(self._discovered))},
        )

    async def _create_entry(self, serial: str) -> config_entries.ConfigFlowResult:
        """Finalize entry creation for selected device."""
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        device_name = self._get_device_name(serial)
        title = f"{device_name} {serial}"

        _LOGGER.info("Discovered and added device: %s", title)

        return self.async_create_entry(
            title=title,
            data={"serial_number": serial},
        )
