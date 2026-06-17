"""The Marantz RS-232 integration."""

from marantz_rs232 import (
    MarantzV2003Receiver,
    MarantzV2007Receiver,
    MarantzV2015Receiver,
    V2003ReceiverState,
    V2007ReceiverState,
    V2015ReceiverState,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .config_flow import MODEL_MODERN, V2003_MODELS, V2007_MODELS
from .const import LOGGER, MarantzReceiver, MarantzRS232ConfigEntry

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(
    hass: HomeAssistant, entry: MarantzRS232ConfigEntry
) -> bool:
    """Set up Marantz RS-232 from a config entry."""
    port = entry.data[CONF_DEVICE]
    model_key = entry.data[CONF_MODEL]

    receiver: MarantzReceiver
    if model_key == MODEL_MODERN:
        receiver = MarantzV2015Receiver(port)
    elif model_key in V2003_MODELS:
        receiver = MarantzV2003Receiver(port)
    else:
        receiver = MarantzV2007Receiver(port, model=V2007_MODELS[model_key])

    try:
        await receiver.connect()
        await receiver.query_state()
    except (ConnectionError, OSError, TimeoutError) as err:
        LOGGER.error("Error connecting to Marantz receiver at %s: %s", port, err)
        if receiver.connected:
            await receiver.disconnect()
        raise ConfigEntryNotReady from err

    entry.runtime_data = receiver

    @callback
    def _on_disconnect(
        state: V2015ReceiverState | V2007ReceiverState | V2003ReceiverState | None,
    ) -> None:
        # Only reload if the entry is still loaded. During entry removal,
        # disconnect() fires this callback but the entry is already gone.
        if state is None and entry.state is ConfigEntryState.LOADED:
            LOGGER.warning("Marantz receiver disconnected, reloading config entry")
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(receiver.subscribe(_on_disconnect))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MarantzRS232ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.disconnect()

    return unload_ok
