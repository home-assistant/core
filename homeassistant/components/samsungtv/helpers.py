"""Helper functions for Samsung TV."""

from collections.abc import Coroutine
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceEntry

from .bridge import SamsungTVBridge
from .const import DOMAIN, ENTRY_RELOAD_COOLDOWN, LOGGER
from .coordinator import SamsungTVConfigEntry


@callback
def async_get_device_entry_by_device_id(
    hass: HomeAssistant, device_id: str
) -> DeviceEntry:
    """Get Device Entry from Device Registry by device ID.

    Raises ValueError if device ID is invalid.
    """
    device_reg = dr.async_get(hass)
    if (device := device_reg.async_get(device_id)) is None:
        raise ValueError(f"Device {device_id} is not a valid {DOMAIN} device.")

    return device


@callback
def async_get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Get device ID from an entity ID.

    Raises ValueError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if (
        entity_entry is None
        or entity_entry.device_id is None
        or entity_entry.platform != DOMAIN
    ):
        raise ValueError(f"Entity {entity_id} is not a valid {DOMAIN} entity.")

    return entity_entry.device_id


@callback
def async_get_client_by_device_entry(
    hass: HomeAssistant, device: DeviceEntry
) -> SamsungTVBridge:
    """Get SamsungTVBridge from Device Registry by device entry.

    Raises ValueError if client is not found.
    """
    entry: SamsungTVConfigEntry | None
    for config_entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(config_entry_id)
        if entry and entry.domain == DOMAIN and entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data.bridge

    raise ValueError(
        f"Device {device.id} is not from an existing {DOMAIN} config entry"
    )


class DebouncedEntryReloader:
    """Reload only after the timer expires."""

    def __init__(self, hass: HomeAssistant, entry: SamsungTVConfigEntry) -> None:
        """Init the debounced entry reloader."""
        self.hass = hass
        self.entry = entry
        self.token = self.entry.data.get(CONF_TOKEN)
        self._debounced_reload: Debouncer[Coroutine[Any, Any, None]] = Debouncer(
            hass,
            LOGGER,
            cooldown=ENTRY_RELOAD_COOLDOWN,
            immediate=False,
            function=self._async_reload_entry,
        )

    async def async_call(
        self, hass: HomeAssistant, entry: SamsungTVConfigEntry
    ) -> None:
        """Start the countdown for a reload."""
        if (new_token := entry.data.get(CONF_TOKEN)) != self.token:
            LOGGER.debug("Skipping reload as its a token update")
            self.token = new_token
            return  # Token updates should not trigger a reload
        LOGGER.debug("Calling debouncer to get a reload after cooldown")
        await self._debounced_reload.async_call()

    @callback
    def async_shutdown(self) -> None:
        """Cancel any pending reload."""
        self._debounced_reload.async_shutdown()

    async def _async_reload_entry(self) -> None:
        """Reload entry."""
        LOGGER.debug("Reloading entry %s", self.entry.title)
        await self.hass.config_entries.async_reload(self.entry.entry_id)
