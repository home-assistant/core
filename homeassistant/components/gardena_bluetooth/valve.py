"""Support for switch entities."""

from __future__ import annotations

from typing import Any

from gardena_bluetooth.const import Valve

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GardenaBluetoothCoordinator
from .entity import GardenaBluetoothEntity

FALLBACK_WATERING_TIME_IN_SECONDS = 60 * 60


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch based on a config entry."""
    coordinator: GardenaBluetoothCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    if GardenaBluetoothValve.characteristics.issubset(coordinator.characteristics):
        entities.append(GardenaBluetoothValve(coordinator))

    async_add_entities(entities)


class GardenaBluetoothValve(GardenaBluetoothEntity, ValveEntity):
    """Representation of a valve switch."""

    _attr_name = None
    _attr_is_closed: bool | None = None
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

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

    def _handle_coordinator_update(self) -> None:
        self._attr_is_closed = not self.coordinator.get_cached(Valve.state)
        super()._handle_coordinator_update()

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        value = (
            self.coordinator.get_cached(Valve.manual_watering_time)
            or FALLBACK_WATERING_TIME_IN_SECONDS
        )
        await self.coordinator.write(Valve.remaining_open_time, value)
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.write(Valve.remaining_open_time, 0)
        self._attr_is_closed = True
        self.async_write_ha_state()
