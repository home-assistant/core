"""Runtime data and helpers for Fritz!Box VPN config entries."""

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from .coordinator import FritzBoxVPNCoordinator

RuntimePlatform = Literal["switch"]


@dataclass
class FritzboxVpnRuntimeData:
    """Per-config-entry runtime state."""

    coordinator: FritzBoxVPNCoordinator
    known_uids_switch: set[str] = field(default_factory=set)
    lock_add_entities_switch: asyncio.Lock = field(default_factory=asyncio.Lock)

    def platform_tracking(
        self, platform: RuntimePlatform
    ) -> tuple[set[str], asyncio.Lock]:
        """Known UIDs set and add-entity lock for a platform."""
        return self.known_uids_switch, self.lock_add_entities_switch

    def clear_known_uids(self, uids: set[str]) -> None:
        """Remove VPN UIDs from platform tracking."""
        if not uids:
            return
        self.known_uids_switch -= uids


type FritzboxVpnConfigEntry = ConfigEntry[FritzboxVpnRuntimeData | None]


def runtime_from_entry(entry: ConfigEntry) -> FritzboxVpnRuntimeData | None:
    """Return typed runtime data from a config entry, if present."""
    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, FritzboxVpnRuntimeData):
        return runtime
    return None


def runtime_from_hass(
    hass: HomeAssistant, entry_id: str
) -> FritzboxVpnRuntimeData | None:
    """Return runtime data for a loaded config entry."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.state != ConfigEntryState.LOADED:
        return None
    return runtime_from_entry(entry)
