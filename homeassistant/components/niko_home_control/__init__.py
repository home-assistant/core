"""The Niko home control integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from nclib.errors import NetcatError
from nhc.controller import NHCController

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import _LOGGER

PLATFORMS: list[Platform] = [Platform.LIGHT]

type NikoHomeControlConfigEntry = ConfigEntry[NikoHomeController]


async def async_setup_entry(
    hass: HomeAssistant, entry: NikoHomeControlConfigEntry
) -> bool:
    """Set Niko Home Control from a config entry."""
    controller = NikoHomeController(entry.data[CONF_HOST])
    try:
        await controller.connect()
    except NetcatError as err:
        raise ConfigEntryNotReady("cannot connect to controller.") from err
    except OSError as err:
        raise ConfigEntryNotReady(
            "unknown error while connecting to controller."
        ) from err

    entry.runtime_data = controller
    controller.add_callback(controller.handle_event)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.minor_version < 2:
        registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(registry, config_entry.entry_id)

        for entry in entries:
            if entry.unique_id.startswith("light-"):
                action_id = entry.unique_id.split("-")[-1]
                new_unique_id = f"{config_entry.entry_id}-{action_id}"
                registry.async_update_entity(
                    entry.entity_id, new_unique_id=new_unique_id
                )

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data}, minor_version=2
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NikoHomeControlConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class NikoHomeController(NHCController):
    """The niko home control controller."""

    def __init__(self, host: str) -> None:
        """Init niko home control controller."""
        super().__init__(host, 8000)
        self._callbacks: dict[str, list[Callable[[int], Awaitable[None]]]] = {}

    def register_callback(
        self, action_id: str, callback: Callable[[int], Awaitable[None]]
    ) -> Callable[[], None]:
        """Register a callback for entity updates."""
        self._callbacks.setdefault(action_id, []).append(callback)

        def remove_callback() -> None:
            self._callbacks[action_id].remove(callback)
            if not self._callbacks[action_id]:
                del self._callbacks[action_id]

        return remove_callback

    async def async_dispatch_update(self, action_id: str, value: int) -> None:
        """Dispatch an update to all registered callbacks."""
        for callback in self._callbacks.get(action_id, []):
            await callback(value)

    async def handle_event(self, event: dict[str, Any]) -> None:
        """Handle an event."""
        await self.async_dispatch_update(event["id"], event["value1"])
