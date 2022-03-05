"""Helper functions for KDE Connect."""
import asyncio

from pykdeconnect.client import KdeConnectClient
from pykdeconnect.devices import KdeConnectDevice
from pykdeconnect.plugin_registry import PluginRegistry

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant

from .const import (
    CONNECT_TIMEOUT,
    DATA_KEY_CLIENT,
    DATA_KEY_DEVICES,
    DATA_KEY_STORAGE,
    DEVICE_NAME,
    DEVICE_TYPE,
    DOMAIN,
)
from .storage import HomeAssistantStorage


async def reject_pairing_request(_: KdeConnectDevice) -> bool:
    """Reject all incoming pairing requests."""
    return False


async def ensure_running(hass: HomeAssistant) -> None:
    """Ensure that the KDE Connect client is running and component data is set up."""
    if DOMAIN not in hass.data:
        device_id = await hass.helpers.instance_id.async_get()

        hass.data[DOMAIN] = {}
        storage = HomeAssistantStorage(hass, device_id)
        client = KdeConnectClient(DEVICE_NAME, DEVICE_TYPE, storage, PluginRegistry())
        hass.data[DOMAIN][DATA_KEY_STORAGE] = storage
        hass.data[DOMAIN][DATA_KEY_CLIENT] = client
        hass.data[DOMAIN][DATA_KEY_DEVICES] = {}

        # We never accept pairing requests. Instead we send pairing requests ourselves.
        client.set_pairing_callback(reject_pairing_request)

        await client.start()
        # Wait a bit to let devices connect before we continue.
        await asyncio.sleep(CONNECT_TIMEOUT)

        async def disconnect_helper(_: Event) -> None:
            await client.stop()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect_helper)
