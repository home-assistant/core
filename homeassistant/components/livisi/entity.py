"""Code for the base class of Livisi entities."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiolivisi.const import CAPABILITY_MAP

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, DOMAIN, LIVISI_REACHABILITY_CHANGE
from .coordinator import LivisiDataUpdateCoordinator


class LivisiEntity(CoordinatorEntity[LivisiDataUpdateCoordinator]):
    """Represents a base livisi entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
        *,
        use_room_as_device_name: bool = False,
        entity_suffix: str | None = None,
    ) -> None:
        """Initialize the common properties of a Livisi device."""
        self.aio_livisi = coordinator.aiolivisi
        self.capabilities: Mapping[str, Any] = device[CAPABILITY_MAP]

        name = device["config"]["name"]
        unique_id = device["id"]
        if entity_suffix:
            name = name + " " + entity_suffix
            unique_id = unique_id + entity_suffix

        room_id: str | None = device.get("location")
        room_name: str | None = None
        if room_id is not None:
            room_name = coordinator.rooms.get(room_id)

        self._attr_available = False
        self._attr_unique_id = unique_id
        self._attr_name = name
        # For livisi climate entities, the device should have the room name from
        # the livisi setup, as each livisi room gets exactly one VRCC device. The entity
        # name will always be some localized value of "Climate", so the full element name
        # in homeassistent will be in the form of "Bedroom Climate"
        device_name = device["config"]["name"]
        if use_room_as_device_name and room_name is not None:
            self._attr_name = name
            device_name = room_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["id"])},
            manufacturer=device["manufacturer"],
            model=device["type"],
            sw_version=device["version"],
            name=device_name,
            suggested_area=room_name,
            via_device=(DOMAIN, config_entry.entry_id),
            configuration_url=f"http://{config_entry.data[CONF_HOST]}/#/device/{device['id']}",
        )
        super().__init__(coordinator)

    async def async_added_to_hass(self) -> None:
        """Register callback for reachability."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_REACHABILITY_CHANGE}_{self.unique_id}",
                self.update_reachability,
            )
        )

    @callback
    def update_reachability(self, is_reachable: bool) -> None:
        """Update the reachability of the device."""
        self._attr_available = is_reachable
        self.async_write_ha_state()
