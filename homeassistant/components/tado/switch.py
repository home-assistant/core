"""Module for Tado child lock switch entity."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TadoConfigEntry
from .entity import TadoDataUpdateCoordinator, TadoZoneEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado switch platform."""

    tado = entry.runtime_data.coordinator
    entities: list[TadoChildLockSwitchEntity] = []
    for zone in tado.zones:
        zoneChildLockSupported = (
            len(zone["devices"]) > 0 and "childLockEnabled" in zone["devices"][0]
        )

        if not zoneChildLockSupported:
            continue

        entities.append(
            TadoChildLockSwitchEntity(
                tado, zone["name"], zone["id"], zone["devices"][0]
            )
        )
    async_add_entities(entities, True)


class TadoChildLockSwitchEntity(TadoZoneEntity, SwitchEntity):
    """Representation of a Tado child lock switch entity."""

    _attr_translation_key = "child_lock"

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        zone_name: str,
        zone_id: int,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the Tado child lock switch entity."""
        super().__init__(zone_name, coordinator.home_id, zone_id, coordinator)

        self._device_info = device_info
        self._device_id = self._device_info["shortSerialNo"]
        self._attr_unique_id = f"{zone_id} {coordinator.home_id} child-lock"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.set_child_lock(self._device_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.set_child_lock(self._device_id, False)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_callback()
        super()._handle_coordinator_update()

    @callback
    def _async_update_callback(self) -> None:
        """Handle update callbacks."""
        try:
            self._device_info = self.coordinator.data["device"][self._device_id]
        except KeyError:
            _LOGGER.error(
                "Could not update child lock info for device %s in zone %s",
                self._device_id,
                self.zone_name,
            )
        else:
            self._attr_is_on = self._device_info.get("childLockEnabled", False) is True
