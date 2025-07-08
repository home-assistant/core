"""__init__.py

Home Assistant integration for Greencell EVSE devices.

This module provides the setup and discovery logic for the Greencell integration:
- Registers the core integration via async_setup and async_setup_entry.
- Subscribes to the GREENCELL_DISC_TOPIC for device "hello"/reset announcements.
- For any newly discovered device (ID not already in hass.data), publishes a QUERY command
  to prompt the device to send its state and configuration.

Key functions:
- async_setup(hass, config):
    Called at Home Assistant startup; installs the reset message listener.
- async_setup_entry(hass, entry):
    Called for each config entry; stores entry data and forwards setups to SENSOR, BUTTON, NUMBER platforms, then re-installs the listener.
- setup_reset_msg_listener(hass):
    Defines and schedules subscription to GREENCELL_DISC_TOPIC, and handles incoming discovery messages by creating an MQTT publish task for unknown devices.
"""

import json
from json import JSONDecodeError
import logging

from homeassistant.components.mqtt import async_subscribe
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    GREENCELL_DISC_TOPIC,
    GreencellHaAccessLevelEnum as AccessLevel,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the GreenCell integration."""
    setup_reset_msg_listener(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GreenCell from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    platforms = [Platform.SENSOR, Platform.BUTTON, Platform.NUMBER]
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    setup_reset_msg_listener(hass)
    return True


def setup_reset_msg_listener(hass: HomeAssistant) -> None:
    """Set up a listener for hello/reset messages from devices."""

    @callback
    def handle_hello_message(message):
        """Handle the hello message from a device."""
        try:
            msg = json.loads(message.payload)
        except JSONDecodeError as e:
            _LOGGER.error("Invalid JSON payload: %s", e)
            return

        device_id = msg.get("id")
        if not device_id:
            _LOGGER.warning("Received message without ID: %s", message.payload)
            return

        try:
            entries = hass.data.get(DOMAIN, {})
            known_ids = [
                entry_data["serial_number"]
                for entry_data in entries.values()
                if "serial_number" in entry_data
            ]
        except KeyError as e:
            _LOGGER.error("Entry data missing expected field: %s", e)
            return
        except AttributeError as e:
            _LOGGER.error("Unexpected structure in hass.data[%s]: %s", DOMAIN, e)
            return

        if device_id in known_ids:
            _LOGGER.info("Device %s is already known", device_id)
            return

        try:
            hass.async_create_task(
                hass.services.async_call(
                    "mqtt",
                    "publish",
                    {
                        "topic": f"/greencell/evse/{device_id}/cmd",
                        "payload": json.dumps({"name": "QUERY"}),
                        "retain": False,
                    },
                )
            )
        except TypeError as e:
            _LOGGER.error("Invalid arguments when creating MQTT task: %s", e)
        except HomeAssistantError as e:
            _LOGGER.error("Home Assistant service error: %s", e)
        except Exception as e:
            _LOGGER.error("Unexpected error publishing QUERY: %s", e)

    async def mqtt_subscribe():
        """Wrapper for async_subscribe to handle the subscription."""
        await async_subscribe(hass, GREENCELL_DISC_TOPIC, handle_hello_message)

    hass.async_create_task(mqtt_subscribe())
