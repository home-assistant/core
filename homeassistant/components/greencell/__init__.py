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


def make_ready_handler(
    serial: str, event: asyncio.Event
) -> Callable[[ReceiveMessage], None]:
    """Create an MQTT message handler that sets event when device matches serial."""

    @callback
    def _on_message(message: ReceiveMessage) -> None:
        if event.is_set():
            return
        try:
            data = json.loads(message.payload)
        except ValueError, TypeError:
            return

        if message.topic == GREENCELL_DISC_TOPIC:
            if data.get("id") != serial:
                return
        elif data.get("id") and data["id"] != serial:
            return

        event.set()

    return _on_message


async def async_setup_entry(hass: HomeAssistant, entry: GreencellConfigEntry) -> bool:
    """Set up Greencell from a config entry."""

    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT integration is not available")

    serial: str = entry.data[CONF_SERIAL_NUMBER]
    device_ready_event = asyncio.Event()
    on_message = make_ready_handler(serial, device_ready_event)

    try:
        unsub_disc = await mqtt.async_subscribe(hass, GREENCELL_DISC_TOPIC, on_message)
        unsub_volt = await mqtt.async_subscribe(
            hass, f"/greencell/evse/{serial}/voltage", on_message
        )
        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                await device_ready_event.wait()
        finally:
            unsub_disc()
            unsub_volt()
    except TimeoutError as err:
        raise ConfigEntryNotReady(f"No initial data from device {serial}") from err
    except HomeAssistantError as err:
        raise ConfigEntryNotReady(f"MQTT error: {err}") from err

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
