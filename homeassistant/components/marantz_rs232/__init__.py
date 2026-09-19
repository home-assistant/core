"""The Marantz RS-232 integration."""

from marantz_rs232 import MarantzV2007Receiver, V2007ReceiverState

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DOMAIN, LOGGER, MarantzRS232ConfigEntry

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(
    hass: HomeAssistant, entry: MarantzRS232ConfigEntry
) -> bool:
    """Set up Marantz RS-232 from a config entry."""
    port = entry.data[CONF_DEVICE]
    receiver = MarantzV2007Receiver(port)

    try:
        await receiver.connect()
        await receiver.query_state()
        await receiver.query_multi_room_a()
    except ValueError as err:
        if receiver.connected:
            await receiver.disconnect()
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_serial_port",
        ) from err
    except (ConnectionError, OSError, TimeoutError) as err:
        if receiver.connected:
            await receiver.disconnect()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
        ) from err

    entry.runtime_data = receiver
    reconnect_requested = False

    @callback
    def _on_disconnect(
        state: V2007ReceiverState | None,
    ) -> None:
        nonlocal reconnect_requested
        if (
            state is None
            and entry.state is ConfigEntryState.LOADED
            and not reconnect_requested
        ):
            reconnect_requested = True
            LOGGER.info("Marantz receiver at %s is unavailable; reconnecting", port)
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
