"""Cover Entity for Genie Garage Door."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from genie_partner_sdk.client import AladdinConnectClient

from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import api
from .const import DOMAIN, SUPPORTED_FEATURES
from .model import GarageDoor

if TYPE_CHECKING:
    from . import AladdinConnectConfigEntry

SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AladdinConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aladdin Connect platform."""
    session: api.AsyncConfigEntryAuth = config_entry.runtime_data
    acc = AladdinConnectClient(session)
    doors = await acc.get_doors()
    if doors is None:
        raise PlatformNotReady("Error from Aladdin Connect getting doors")
    device_registry = dr.async_get(hass)
    doors_to_add = []
    for door in doors:
        existing = device_registry.async_get_device({(DOMAIN, door.unique_id)})
        if existing is None:
            doors_to_add.append(door)

    async_add_entities(
        (AladdinDevice(acc, door, config_entry) for door in doors_to_add),
    )
    remove_stale_devices(hass, config_entry, doors)


def remove_stale_devices(
    hass: HomeAssistant,
    config_entry: AladdinConnectConfigEntry,
    devices: list[GarageDoor],
) -> None:
    """Remove stale devices from device registry."""
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    all_device_ids = {door.unique_id for door in devices}

    for device_entry in device_entries:
        device_id: str | None = None
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_id = identifier[1]
                break

        if device_id and device_id not in all_device_ids:
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=config_entry.entry_id
            )


class AladdinDevice(CoverEntity):
    """Representation of Aladdin Connect cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_has_entity_name = True
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_name = None

    def __init__(
        self,
        acc: AladdinConnectClient,
        device: GarageDoor,
        entry: AladdinConnectConfigEntry,
    ) -> None:
        """Initialize the Aladdin Connect cover."""
        self._acc = acc
        self._device_id = device.device_id
        self._number = device.door_number
        self._cached_door_status: str | None = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer="Overhead Door",
        )
        self._attr_unique_id = device.unique_id

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Issue open command to cover."""
        await self._acc.open_door(self._device_id, self._number)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Issue close command to cover."""
        await self._acc.close_door(self._device_id, self._number)

    async def async_update(self) -> None:
        """Update status of cover."""
        await self._acc.update_door(self._device_id, self._number)
        # Cache the door status to avoid redundant API calls
        self._cached_door_status = self._acc.get_door_status(
            self._device_id, self._number
        )

    def _get_door_status(self) -> str | None:
        """Get cached door status."""
        return self._cached_door_status

    @property
    def is_closed(self) -> bool | None:
        """Update is closed attribute."""
        value = self._get_door_status()
        if value is None:
            return None
        return bool(value == "closed")

    @property
    def is_closing(self) -> bool | None:
        """Update is closing attribute."""
        value = self._get_door_status()
        if value is None:
            return None
        return bool(value == "closing")

    @property
    def is_opening(self) -> bool | None:
        """Update is opening attribute."""
        value = self._get_door_status()
        if value is None:
            return None
        return bool(value == "opening")
