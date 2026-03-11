"""Home Assistant integration for Greencell EVSE devices."""

import asyncio
from collections.abc import Callable
import json
import logging

from greencell_client.access import GreencellAccess, GreencellHaAccessLevel
from greencell_client.elec_data import ElecData3Phase, ElecDataSinglePhase

from homeassistant.components import mqtt
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

from .const import CONF_SERIAL_NUMBER, DISCOVERY_TIMEOUT, GREENCELL_DISC_TOPIC
from .models import GreencellConfigEntry, GreencellRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def wait_for_device_ready(
    hass: HomeAssistant,
    serial: str,
) -> tuple[Callable[[], None], asyncio.Event]:
    """Subscribe to GREENCELL_DISC_TOPIC and device voltage topic.

    Return (unsubscribe_all, event) where event is set on first message.
    """
    event = asyncio.Event()
    unsub_disc: Callable[[], None] | None = None
    unsub_volt: Callable[[], None] | None = None

    @callback
    def _on_message(message: ReceiveMessage) -> None:
        """Handle readiness message."""
        if event.is_set():
            return

        try:
            data = json.loads(message.payload)
            if "id" in data and data["id"] != serial:
                return
        except ValueError, TypeError:
            _LOGGER.debug("Received invalid JSON on readiness topic, ignoring")
            return

        event.set()
        _LOGGER.debug("Received initial valid message for device %s", serial)

    try:
        unsub_disc = await mqtt.async_subscribe(hass, GREENCELL_DISC_TOPIC, _on_message)
        topic = f"/greencell/evse/{serial}/voltage"
        unsub_volt = await mqtt.async_subscribe(hass, topic, _on_message)
    except HomeAssistantError as err:
        _LOGGER.error("Failed to subscribe for readiness check: %s", err)
        if unsub_disc:
            unsub_disc()
        raise ConfigEntryNotReady(f"MQTT subscription failed: {err}") from err

    def _unsubscribe_all() -> None:
        """Safe cleanup of subscriptions."""
        nonlocal unsub_disc, unsub_volt
        if unsub_disc:
            unsub_disc()
            unsub_disc = None  # Prevent double unsubscription
        if unsub_volt:
            unsub_volt()
            unsub_volt = None

    return _unsubscribe_all, event


async def async_setup_entry(hass: HomeAssistant, entry: GreencellConfigEntry) -> bool:
    """Set up Greencell from a config entry with test-before-setup and runtime_data."""

    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT integration is not available")

    serial: str = entry.data[CONF_SERIAL_NUMBER]
    unsub, device_ready_event = await wait_for_device_ready(hass, serial)
    try:
        async with asyncio.timeout(DISCOVERY_TIMEOUT):
            await device_ready_event.wait()
    except TimeoutError as err:
        unsub()
        raise ConfigEntryNotReady(
            f"No initial data from device {serial} within {DISCOVERY_TIMEOUT}s"
        ) from err
    finally:
        unsub()

    entry.runtime_data = GreencellRuntimeData(
        access=GreencellAccess(GreencellHaAccessLevel.EXECUTE),
        current_data=ElecData3Phase(),
        voltage_data=ElecData3Phase(),
        power_data=ElecDataSinglePhase(),
        state_data=ElecDataSinglePhase(),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GreencellConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
