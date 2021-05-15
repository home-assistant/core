"""Support for Bond covers."""
from __future__ import annotations

from typing import Any

from bond_api import Action, BPUPSubscriptions, DeviceType

from homeassistant.components.cover import DEVICE_CLASS_SHADE, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BPUP_SUBS, DOMAIN, HUB
from .entity import BondEntity
from .utils import BondDevice, BondHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond cover devices."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: BondHub = data[HUB]
    bpup_subs: BPUPSubscriptions = data[BPUP_SUBS]

    covers: list[Entity] = [
        BondCover(hub, device, bpup_subs)
        for device in hub.devices
        if device.type == DeviceType.MOTORIZED_SHADES
    ]

    async_add_entities(covers, True)


class BondCover(BondEntity, CoverEntity):
    """Representation of a Bond cover."""

    def __init__(
        self, hub: BondHub, device: BondDevice, bpup_subs: BPUPSubscriptions
    ) -> None:
        """Create HA entity representing Bond cover."""
        super().__init__(hub, device, bpup_subs)

        self._closed: bool | None = None

    def _apply_state(self, state: dict) -> None:
        cover_open = state.get("open")
        self._closed = True if cover_open == 0 else False if cover_open == 1 else None

    @property
    def device_class(self) -> str | None:
        """Get device class."""
        return DEVICE_CLASS_SHADE

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self._closed

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._hub.bond.action(self._device.device_id, Action.open())

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._hub.bond.action(self._device.device_id, Action.close())

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Hold cover."""
        await self._hub.bond.action(self._device.device_id, Action.hold())
