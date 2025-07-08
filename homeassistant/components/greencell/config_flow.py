"""config_flow.py

Config flow for Greencell EVSE integration in Home Assistant.

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

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback

from .const import (
    DISCOVERY_TIMEOUT,
    DOMAIN,
    GREENCELL_BROADCAST_TOPIC,
    GREENCELL_DISC_TOPIC,
    GREENCELL_HABU_DEN,
    GREENCELL_HABU_DEN_SERIAL_PREFIX,
    GREENCELL_OTHER_DEVICE,
)

_LOGGER = logging.getLogger(__name__)


class EVSEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for EVSE device."""

    VERSION = 1

    def __init__(self):
        self.discovery_event = asyncio.Event()
        self.discovery_data = None
        self._remove_listener = None

    def get_device_name(self, serial_number: str) -> str:
        """Get device name based on serial number."""
        if serial_number.startswith(GREENCELL_HABU_DEN_SERIAL_PREFIX):
            return GREENCELL_HABU_DEN
        return GREENCELL_OTHER_DEVICE

    async def _publish_disc_request(self):
        """Publish a discovery request to the MQTT topic."""
        payload = json.dumps({"name": "BROADCAST"})
        await mqtt.async_publish(self.hass, GREENCELL_BROADCAST_TOPIC, payload, 0, True)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""

        self._remove_listener = await mqtt.async_subscribe(
            self.hass, GREENCELL_DISC_TOPIC, self._mqtt_message_received
        )

        await self._publish_disc_request()

        try:
            await asyncio.wait_for(
                self.discovery_event.wait(), timeout=DISCOVERY_TIMEOUT
            )
        except TimeoutError:
            _LOGGER.warning("Device discovery timed out")
            return self.async_abort(reason="discovery_timeout")
        finally:
            if self._remove_listener:
                self._remove_listener()

        discovery_payload = self.discovery_data
        serial_number = discovery_payload.get("id")

        if not serial_number:
            _LOGGER.error("Invalid discovery payload: {discovery_payload}")
            return self.async_abort(reason="invalid_discovery_data")

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()

        _LOGGER.info("Device %s successfully added via config flow", serial_number)

        dev_name = self.get_device_name(serial_number)
        return self.async_create_entry(
            title=f"{dev_name} {serial_number}",
            data={
                "serial_number": serial_number,
            },
        )

    @callback
    def _mqtt_message_received(self, msg):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(msg.payload)
            self.discovery_data = payload
            self.discovery_event.set()
        except json.JSONDecodeError:
            _LOGGER.error("Failed to decode MQTT message payload: %s", msg.payload)
