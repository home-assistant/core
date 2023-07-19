"""Support for number entities."""
from __future__ import annotations

from dataclasses import dataclass, field

from gardena_bluetooth.const import DeviceConfiguration, Valve
from gardena_bluetooth.parse import (
    CharacteristicInt,
    CharacteristicLong,
    CharacteristicUInt16,
)

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    Coordinator,
    GardenaBluetoothDescriptorEntity,
    GardenaBluetoothEntity,
)


@dataclass
class GardenaBluetoothNumberEntityDescription(NumberEntityDescription):
    """Description of entity."""

    char: CharacteristicInt | CharacteristicUInt16 | CharacteristicLong = field(
        default_factory=lambda: CharacteristicInt("")
    )


DESCRIPTIONS = (
    GardenaBluetoothNumberEntityDescription(
        key=Valve.manual_watering_time.uuid,
        translation_key="manual_watering_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        native_min_value=0.0,
        native_max_value=24 * 60 * 60,
        native_step=60,
        entity_category=EntityCategory.CONFIG,
        char=Valve.manual_watering_time,
    ),
    GardenaBluetoothNumberEntityDescription(
        key=Valve.remaining_open_time.uuid,
        translation_key="remaining_open_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0.0,
        native_max_value=24 * 60 * 60,
        native_step=60.0,
        entity_category=EntityCategory.DIAGNOSTIC,
        char=Valve.remaining_open_time,
    ),
    GardenaBluetoothNumberEntityDescription(
        key=DeviceConfiguration.rain_pause.uuid,
        translation_key="rain_pause",
        native_unit_of_measurement=UnitOfTime.DAYS,
        mode=NumberMode.BOX,
        native_min_value=0.0,
        native_max_value=127.0,
        native_step=1.0,
        entity_category=EntityCategory.CONFIG,
        char=DeviceConfiguration.rain_pause,
    ),
    GardenaBluetoothNumberEntityDescription(
        key=DeviceConfiguration.season_pause.uuid,
        translation_key="season_pause",
        native_unit_of_measurement=UnitOfTime.DAYS,
        mode=NumberMode.BOX,
        native_min_value=0.0,
        native_max_value=365.0,
        native_step=1.0,
        entity_category=EntityCategory.CONFIG,
        char=DeviceConfiguration.season_pause,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entity based on a config entry."""
    coordinator: Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [
        GardenaBluetoothNumber(coordinator, description)
        for description in DESCRIPTIONS
        if description.key in coordinator.characteristics
    ]
    if Valve.remaining_open_time.uuid in coordinator.characteristics:
        entities.append(GardenaBluetoothRemainingOpenSetNumber(coordinator))
    async_add_entities(entities)


class GardenaBluetoothNumber(GardenaBluetoothDescriptorEntity, NumberEntity):
    """Representation of a number."""

    entity_description: GardenaBluetoothNumberEntityDescription

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.get_cached(self.entity_description.char)
        if data is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = float(data)
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.write(self.entity_description.char, int(value))
        self.async_write_ha_state()


class GardenaBluetoothRemainingOpenSetNumber(GardenaBluetoothEntity, NumberEntity):
    """Representation of a entity with remaining time."""

    _attr_translation_key = "remaining_open_set"
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0.0
    _attr_native_max_value = 24 * 60
    _attr_native_step = 1.0

    def __init__(
        self,
        coordinator: Coordinator,
    ) -> None:
        """Initialize the remaining time entity."""
        super().__init__(coordinator, {Valve.remaining_open_time.uuid})
        self._attr_unique_id = f"{coordinator.address}-remaining_open_set"

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.write(Valve.remaining_open_time, int(value * 60))
        self.async_write_ha_state()
