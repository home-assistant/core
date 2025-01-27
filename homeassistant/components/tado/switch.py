"""Module for Tado child lock switch entity."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TadoConfigEntry
from .const import TYPE_HEATING
from .entity import TadoDataUpdateCoordinator, TadoZoneEntity

_LOGGER = logging.getLogger(__name__)

TRANSLATION_KEY = "child_lock"


class TadoChildLockSwitchEntity(TadoZoneEntity, SwitchEntity):
    """Representation of a Tado child lock switch entity."""

    _attr_unique_id: str | None = None

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        zone_name: str,
        zone_id: int,
        device_info,
    ) -> None:
        """Initialize the Tado child lock switch entity."""
        super().__init__(zone_name, coordinator.home_id, zone_id, coordinator)

        self._device_info = device_info
        self._device_id = self._device_info["shortSerialNo"]
        self._state: bool | None = None
        self._attr_unique_id = f"{zone_name}-child-lock"

    @property
    def translation_key(self) -> str:
        """Return the translation key."""
        return TRANSLATION_KEY

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        return self._state

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
            return
        self._state = self._device_info.get("childLockEnabled", False) is True


async def async_setup_entry(
    hass: HomeAssistant, entry: TadoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tado climate platform."""

    tado = entry.runtime_data.coordinator
    entities: list[TadoChildLockSwitchEntity] = await _generate_entities(tado)

    async_add_entities(entities, True)


async def _generate_entities(
    tado: TadoDataUpdateCoordinator,
) -> list[TadoChildLockSwitchEntity]:
    """Create all climate entities."""
    entities: list[TadoChildLockSwitchEntity] = []
    for zone in tado.zones:
        zoneChildLockSupported = (
            zone["type"] in [TYPE_HEATING]
            and len(zone["devices"]) > 0
            and "childLockEnabled" in zone["devices"][0]
        )

        if not zoneChildLockSupported:
            continue

        entities.append(
            TadoChildLockSwitchEntity(
                tado, zone["name"], zone["id"], zone["devices"][0]
            )
        )
    return entities
