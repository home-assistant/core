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
        zone_child_lock_supported_devices = filter_child_lock_enabled_devices_in_zone(
            zone
        )

        has_any_supported_child_lock_devices = (
            len(zone_child_lock_supported_devices) > 0
        )

        if not has_any_supported_child_lock_devices:
            continue

        entities.append(
            TadoChildLockSwitchEntity(
                tado, zone["name"], zone["id"], zone_child_lock_supported_devices
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
        device_infos: list[dict[str, Any],],
    ) -> None:
        """Initialize the Tado child lock switch entity."""
        super().__init__(zone_name, coordinator.home_id, zone_id, coordinator)
        self._zone_device_infos = device_infos
        self._attr_unique_id = f"{zone_id} {coordinator.home_id} child-lock"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        for device in self._zone_device_infos:
            await self.coordinator.set_child_lock(device["shortSerialNo"], True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        for device in self._zone_device_infos:
            await self.coordinator.set_child_lock(device["shortSerialNo"], False)
        await self.coordinator.async_request_refresh()

    def get_aggregated_state(self) -> bool:
        """Return the active child lock state by all supported devices in zone."""
        return all(
            device_info.get("childLockEnabled", False) is True
            for device_info in self._zone_device_infos
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_callback()
        super()._handle_coordinator_update()

    @callback
    def _async_update_callback(self) -> None:
        """Handle update callbacks."""
        try:
            zone = next(
                zone for zone in self.coordinator.zones if zone["id"] == self.zone_id
            )
            self._zone_device_infos = filter_child_lock_enabled_devices_in_zone(zone)
        except KeyError:
            _LOGGER.error(
                "Could not update child lock info for devices in zone %s",
                self.zone_name,
            )
        else:
            self._attr_is_on = self.get_aggregated_state()


def filter_child_lock_enabled_devices_in_zone(zone):
    """Return child lock enabled devices in given zone."""

    return [device for device in zone["devices"] if "childLockEnabled" in device]
