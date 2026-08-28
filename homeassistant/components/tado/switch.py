"""Module for Tado child lock switch entity."""

import logging
from typing import Any, override

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import TadoConfigEntry, TadoDataUpdateCoordinator
from .entity import TadoDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado switch platform."""

    tado = entry.runtime_data
    entity_registry = er.async_get(hass)

    # Child lock used to be represented as a zone entity, even though the Tado API
    # exposes and controls it per device. Migrate existing entities to device-based
    # unique IDs so users keep their existing entity IDs and customizations.
    for zone in tado.zones:
        if not zone["devices"]:
            continue

        device = zone["devices"][0]
        if "childLockEnabled" not in device:
            continue

        old_unique_id = f"{zone['id']} {tado.home_id} child-lock"
        new_unique_id = f"{device['shortSerialNo']} {tado.home_id} child-lock"
        entity_id = entity_registry.async_get_entity_id(
            SWITCH_DOMAIN, DOMAIN, old_unique_id
        )
        if entity_id is not None and entity_registry.async_get_entity_id(
            SWITCH_DOMAIN, DOMAIN, new_unique_id
        ) is None:
            _LOGGER.debug(
                "Migrating Tado child lock entity %s from zone %s to device %s",
                entity_id,
                zone["id"],
                device["shortSerialNo"],
            )
            entity_registry.async_update_entity(
                entity_id, new_unique_id=new_unique_id
            )

    async_add_entities(
        [
            TadoChildLockSwitchEntity(tado, device)
            for device in tado.devices
            if "childLockEnabled" in device
        ],
        True,
    )


class TadoChildLockSwitchEntity(TadoDeviceEntity, SwitchEntity):
    """Representation of a Tado child lock switch entity."""

    _attr_translation_key = "child_lock"

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the Tado child lock switch entity."""
        super().__init__(device_info, coordinator)

        self._attr_unique_id = f"{self.device_id} {coordinator.home_id} child-lock"

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.set_child_lock(self.device_id, True)
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.set_child_lock(self.device_id, False)
        await self.coordinator.async_request_refresh()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_callback()
        super()._handle_coordinator_update()

    @callback
    def _async_update_callback(self) -> None:
        """Handle update callbacks."""
        try:
            self._device_info = self.coordinator.data["device"][self.device_id]
        except KeyError:
            _LOGGER.error(
                "Could not update child lock info for device %s", self.device_id
            )
        else:
            self._attr_is_on = self._device_info.get("childLockEnabled", False) is True
