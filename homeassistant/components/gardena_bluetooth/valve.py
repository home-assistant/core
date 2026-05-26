"""Support for valve entities."""

from typing import Any

from gardena_bluetooth.const import Valve, Valve1, Valve2, ValveX

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import WATERING_COMMAND_SOURCE
from .coordinator import GardenaBluetoothConfigEntry, GardenaBluetoothCoordinator
from .entity import GardenaBluetoothEntity

FALLBACK_WATERING_TIME_IN_SECONDS = 60 * 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenaBluetoothConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up valve entities based on a config entry."""
    coordinator = entry.runtime_data
    entities: list[ValveEntity] = []

    if GardenaBluetoothValve.characteristics.issubset(coordinator.characteristics):
        entities.append(GardenaBluetoothValve(coordinator))

    for entity_cls in (GardenaBluetoothValve1, GardenaBluetoothValve2):
        if entity_cls.characteristics.issubset(coordinator.characteristics):
            entities.append(entity_cls(coordinator))

    async_add_entities(entities)


class GardenaBluetoothValve(GardenaBluetoothEntity, ValveEntity):
    """Old single-valve Bluetooth-only Water Control (e.g. 01889-20)."""

    _attr_name = None
    _attr_is_closed: bool | None = None
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_device_class = ValveDeviceClass.WATER

    characteristics = {
        Valve.state.unique_id,
        Valve.manual_watering_time.unique_id,
        Valve.remaining_open_time.unique_id,
    }

    def __init__(
        self,
        coordinator: GardenaBluetoothCoordinator,
    ) -> None:
        """Initialize the valve."""
        super().__init__(
            coordinator, {Valve.state.uuid, Valve.manual_watering_time.uuid}
        )
        self._attr_unique_id = f"{coordinator.address}-{Valve.state.unique_id}"

    def _handle_coordinator_update(self) -> None:
        self._attr_is_closed = not self.coordinator.get_cached(Valve.state)
        super()._handle_coordinator_update()

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve for the configured manual watering time."""
        value = (
            self.coordinator.get_cached(Valve.manual_watering_time)
            or FALLBACK_WATERING_TIME_IN_SECONDS
        )
        await self.coordinator.write(Valve.remaining_open_time, value)
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self.coordinator.write(Valve.remaining_open_time, 0)
        self._attr_is_closed = True
        self.async_write_ha_state()


class GardenaBluetoothValveX(GardenaBluetoothEntity, ValveEntity):
    """Base for the Smart Water Control family (Valve1/Valve2 GATT services)."""

    _service: type[ValveX]
    characteristics: set[str]

    _attr_is_closed: bool | None = None
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_device_class = ValveDeviceClass.WATER

    def __init__(
        self,
        coordinator: GardenaBluetoothCoordinator,
    ) -> None:
        """Initialize the valve."""
        super().__init__(
            coordinator,
            {
                self._service.state.uuid,
                self._service.manual_watering_duration.uuid,
                self._service.remaining_time_open.uuid,
                self._service.available.uuid,
            },
        )
        self._attr_unique_id = f"{coordinator.address}-{self._service.state.unique_id}"

    def _handle_coordinator_update(self) -> None:
        self._attr_is_closed = not self.coordinator.get_cached(self._service.state)
        super()._handle_coordinator_update()

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve for the configured manual watering duration."""
        cached = self.coordinator.get_cached(self._service.manual_watering_duration)
        duration = cached if cached is not None else FALLBACK_WATERING_TIME_IN_SECONDS
        await self.coordinator.write(
            self._service.start_watering,
            {0: WATERING_COMMAND_SOURCE, 1: str(duration)},
        )
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self.coordinator.write(
            self._service.stop_watering,
            {0: WATERING_COMMAND_SOURCE},
        )
        self._attr_is_closed = True
        self.async_write_ha_state()


class GardenaBluetoothValve1(GardenaBluetoothValveX):
    """Valve1 entity (G-19033 wc_single, valve 1 of G-19034 wc_dual)."""

    _service = Valve1
    _attr_translation_key = "valve_1"
    characteristics = {
        Valve1.state.unique_id,
        Valve1.start_watering.unique_id,
        Valve1.stop_watering.unique_id,
    }


class GardenaBluetoothValve2(GardenaBluetoothValveX):
    """Valve2 entity (G-19034 wc_dual second valve)."""

    _service = Valve2
    _attr_translation_key = "valve_2"
    characteristics = {
        Valve2.state.unique_id,
        Valve2.start_watering.unique_id,
        Valve2.stop_watering.unique_id,
    }
