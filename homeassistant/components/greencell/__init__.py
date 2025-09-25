"""Home Assistant integration for Greencell EVSE devices.

This module provides the setup and discovery logic for the Greencell integration:
- Registers the core integration via async_setup and async_setup_entry.
- Subscribes to the GREENCELL_DISC_TOPIC for device "hello"/reset announcements.
- For any newly discovered device (ID not already configured), publishes a QUERY command
  to prompt the device to send its state and configuration.

Key functions:
- async_setup(hass, config):
    Called at Home Assistant startup; installs the discovery listener.
- async_setup_entry(hass, entry):
    Called for each config entry; waits for first device message, stores runtime_data,
    forwards setups to SENSOR platform.
- setup_discovery_listener(hass):
    Defines and schedules subscription to GREENCELL_DISC_TOPIC for new devices.
- wait_for_device_ready(hass, serial, timeout):
    Subscribes to both DISC_TOPIC and device voltage topic, waits for first message.
"""

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from greencell_client.access import GreencellAccess, GreencellHaAccessLevel
from greencell_client.elec_data import ElecData3Phase, ElecDataSinglePhase

from homeassistant.components import mqtt
from homeassistant.components.mqtt import async_subscribe
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

from .const import (
    CONF_SERIAL_NUMBER,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    GREENCELL_ACCESS_KEY,
    GREENCELL_CURRENT_DATA_KEY,
    GREENCELL_DISC_TOPIC,
    GREENCELL_POWER_DATA_KEY,
    GREENCELL_STATE_DATA_KEY,
    GREENCELL_VOLTAGE_DATA_KEY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


def wait_for_device_ready(
    hass: HomeAssistant, serial: str, timeout: float
) -> tuple[Callable[[], None], asyncio.Event]:
    """Subscribe to GREENCELL_DISC_TOPIC and device voltage topic.

    Return (unsubscribe_all, event) where event is set on first message.
    """
    event = asyncio.Event()
    unsub_disc: Callable[[], None] | None = None
    unsub_volt: Callable[[], None] | None = None

    @callback
    def _on_message(message: Any) -> None:
        if not event.is_set():
            event.set()
            _LOGGER.debug("Received initial message for device %s", serial)

    async def _async_subscribe_all() -> None:
        nonlocal unsub_disc, unsub_volt
        try:
            unsub_disc = await async_subscribe(hass, GREENCELL_DISC_TOPIC, _on_message)
        except HomeAssistantError:
            _LOGGER.error("Cannot subscribe to discovery topic for readiness check")
        try:
            topic = f"/greencell/evse/{serial}/voltage"
            unsub_volt = await async_subscribe(hass, topic, _on_message)
        except HomeAssistantError:
            _LOGGER.error(
                "Cannot subscribe to voltage topic %s for readiness check", topic
            )

    hass.async_create_task(_async_subscribe_all())

    def _unsubscribe_all() -> None:
        if unsub_disc:
            unsub_disc()
        if unsub_volt:
            unsub_volt()

    return _unsubscribe_all, event


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Greencell from a config entry with test-before-setup and runtime_data."""

    await mqtt.async_wait_for_mqtt_client(hass)

    serial = entry.data.get(CONF_SERIAL_NUMBER)
    if not serial:
        raise ConfigEntryNotReady("Missing serial_number in config entry")

    unsub_ready, ready_event = wait_for_device_ready(hass, serial, DISCOVERY_TIMEOUT)
    try:
        await asyncio.wait_for(ready_event.wait(), timeout=DISCOVERY_TIMEOUT)
    except TimeoutError as err:
        unsub_ready()
        raise ConfigEntryNotReady(
            f"No initial data from device {serial} within {DISCOVERY_TIMEOUT}s"
        ) from err
    unsub_ready()

    runtime = {
        GREENCELL_ACCESS_KEY: GreencellAccess(GreencellHaAccessLevel.EXECUTE),
        GREENCELL_CURRENT_DATA_KEY: ElecData3Phase(),
        GREENCELL_VOLTAGE_DATA_KEY: ElecData3Phase(),
        GREENCELL_POWER_DATA_KEY: ElecDataSinglePhase(),
        GREENCELL_STATE_DATA_KEY: ElecDataSinglePhase(),
    }
    entry.runtime_data = runtime
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up resources."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
