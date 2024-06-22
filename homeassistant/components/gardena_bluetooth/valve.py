"""Support for switch entities."""

from __future__ import annotations

from typing import Any

from gardena_bluetooth.const import Valve

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import Coordinator, GardenaBluetoothEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch based on a config entry."""
    coordinator: Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    if GardenaBluetoothValve.characteristics.issubset(coordinator.characteristics):
        entities.append(GardenaBluetoothValve(coordinator))

    async_add_entities(entities)


class GardenaBluetoothValve(GardenaBluetoothEntity, ValveEntity):
    """Representation of a valve switch."""

    characteristics = {
        Valve.state.uuid,
        Valve.manual_watering_time.uuid,
        Valve.remaining_open_time.uuid,
    }

    def __init__(
        self,
        coordinator: Coordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            coordinator, {Valve.state.uuid, Valve.manual_watering_time.uuid}
        )
        self._attr_unique_id = f"{coordinator.address}-{Valve.state.uuid}"
        self._attr_name = None
        self._attr_is_closed = None
        self._attr_reports_position = False
        self._attr_supported_features = (
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        )

    def _handle_coordinator_update(self) -> None:
        is_open = self.coordinator.get_cached(Valve.state)
        if is_open is None:
            self._attr_is_closed = None
        else:
            self._attr_is_closed = not is_open
        super()._handle_coordinator_update()

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if (value := self.coordinator.get_cached(Valve.manual_watering_time)) is None:
            raise HomeAssistantError("Unable to get manual activation time.")

        await self.coordinator.write(Valve.remaining_open_time, value)
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.write(Valve.remaining_open_time, 0)
        self._attr_is_closed = True
        self.async_write_ha_state()
