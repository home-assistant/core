"""Code to handle a Livisi switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    LIVISI_REACHABILITY_CHANGE,
    LIVISI_STATE_CHANGE,
    LOGGER,
    PSS_DEVICE_TYPE,
)
from .coordinator import LivisiDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def handle_coordinator_update() -> None:
        """Add switch."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[SwitchEntity] = []
        for device in shc_devices:
            if (
                device["type"] == PSS_DEVICE_TYPE
                and device["id"] not in coordinator.devices
            ):
                livisi_switch: SwitchEntity = create_entity(
                    config_entry, device, coordinator
                )
                LOGGER.debug("Include device type: %s", device["type"])
                coordinator.devices.add(device["id"])
                entities.append(livisi_switch)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


def create_entity(
    config_entry: ConfigEntry,
    device: dict[str, Any],
    coordinator: LivisiDataUpdateCoordinator,
) -> SwitchEntity:
    """Create Switch Entity."""
    config_details: dict[str, Any] = device["config"]
    capabilities: list = device["capabilities"]
    room_id: str = device["location"]
    room_name: str = coordinator.rooms[room_id]
    livisi_switch = LivisiSwitch(
        config_entry,
        coordinator,
        unique_id=device["id"],
        manufacturer=device["manufacturer"],
        device_type=device["type"],
        name=config_details["name"],
        capability_id=capabilities[0],
        room=room_name,
    )
    return livisi_switch


class LivisiSwitch(CoordinatorEntity[LivisiDataUpdateCoordinator], SwitchEntity):
    """Represents the Livisi Switch."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        unique_id: str,
        manufacturer: str,
        device_type: str,
        name: str,
        capability_id: str,
        room: str,
    ) -> None:
        """Initialize the Livisi Switch."""
        self.config_entry = config_entry
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._capability_id = capability_id
        self.aio_livisi = coordinator.aiolivisi
        self._attr_available = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=manufacturer,
            model=device_type,
            name=name,
            suggested_area=room,
            via_device=(DOMAIN, config_entry.entry_id),
        )
        super().__init__(coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        response = await self.aio_livisi.async_pss_set_state(
            self._capability_id, is_on=True
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn on {self._attr_name}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        response = await self.aio_livisi.async_pss_set_state(
            self._capability_id, is_on=False
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        response = await self.coordinator.async_get_pss_state(self._capability_id)
        if response is None:
            self._attr_is_on = False
            self._attr_available = False
        else:
            self._attr_is_on = response
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._capability_id}",
                self.update_states,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_REACHABILITY_CHANGE}_{self.unique_id}",
                self.update_reachability,
            )
        )

    @callback
    def update_states(self, state: bool) -> None:
        """Update the states of the switch device."""
        self._attr_is_on = state
        self.async_write_ha_state()

    @callback
    def update_reachability(self, is_reachable: bool) -> None:
        """Update the reachability of the switch device."""
        self._attr_available = is_reachable
        self.async_write_ha_state()
