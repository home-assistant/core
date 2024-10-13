"""Support for switch entities."""

from __future__ import annotations

from typing import Any

from gardena_bluetooth.const import Valve

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GardenaBluetoothCoordinator
from .entity import GardenaBluetoothEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch based on a config entry."""
    coordinator: GardenaBluetoothCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    if GardenaBluetoothValveSwitch.characteristics.issubset(
        coordinator.characteristics
    ):
        entities.append(GardenaBluetoothValveSwitch(coordinator))

    async_add_entities(entities)


class GardenaBluetoothValveSwitch(GardenaBluetoothEntity, SwitchEntity):
    """Representation of a valve switch."""

    characteristics = {
        Valve.state.uuid,
        Valve.manual_watering_time.uuid,
        Valve.remaining_open_time.uuid,
    }

    def __init__(
        self,
        coordinator: GardenaBluetoothCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            coordinator, {Valve.state.uuid, Valve.manual_watering_time.uuid}
        )
        self._attr_unique_id = f"{coordinator.address}-{Valve.state.uuid}"
        self._attr_translation_key = "state"
        self._attr_is_on = None
        self._attr_entity_registry_enabled_default = False

    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self.coordinator.get_cached(Valve.state)
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if not (data := self.coordinator.data.get(Valve.manual_watering_time.uuid)):
            raise HomeAssistantError("Unable to get manual activation time.")

        value = Valve.manual_watering_time.decode(data)
        await self.coordinator.write(Valve.remaining_open_time, value)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.write(Valve.remaining_open_time, 0)
        self._attr_is_on = False
        self.async_write_ha_state()
