"""Support for Sure PetCare Flaps/Pets sensors."""

from __future__ import annotations

from typing import cast

from surepy.entities import SurepyEntity
from surepy.entities.devices import Felaqua as SurepyFelaqua
from surepy.entities.pet import Pet as SurepyPet
from surepy.enums import EntityType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VOLTAGE, PERCENTAGE, EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SURE_BATT_VOLTAGE_DIFF, SURE_BATT_VOLTAGE_LOW
from .coordinator import SurePetcareDataCoordinator
from .entity import SurePetcareEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sure PetCare Flaps sensors."""

    entities: list[SurePetcareEntity] = []

    coordinator: SurePetcareDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    for surepy_entity in coordinator.data.values():
        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(SureBattery(surepy_entity.id, coordinator))

        if surepy_entity.type == EntityType.FELAQUA:
            entities.append(Felaqua(surepy_entity.id, coordinator))
        if surepy_entity.type == EntityType.PET:
            entities.append(PetLastSeenFlapDevice(surepy_entity.id, coordinator))
            entities.append(PetLastSeenUser(surepy_entity.id, coordinator))

    async_add_entities(entities)


class SureBattery(SurePetcareEntity, SensorEntity):
    """A sensor implementation for Sure Petcare batteries."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, surepetcare_id: int, coordinator: SurePetcareDataCoordinator
    ) -> None:
        """Initialize a Sure Petcare battery sensor."""
        super().__init__(surepetcare_id, coordinator)

        self._attr_name = f"{self._device_name} Battery Level"
        self._attr_unique_id = f"{self._device_id}-battery"

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Update the state and attributes."""
        state = surepy_entity.raw_data()["status"]

        try:
            per_battery_voltage = state["battery"] / 4
            voltage_diff = per_battery_voltage - SURE_BATT_VOLTAGE_LOW
            self._attr_native_value = max(
                0, min(int(voltage_diff / SURE_BATT_VOLTAGE_DIFF * 100), 100)
            )
        except KeyError, TypeError:
            self._attr_native_value = None

        if state:
            voltage_per_battery = float(state["battery"]) / 4
            self._attr_extra_state_attributes = {
                ATTR_VOLTAGE: f"{float(state['battery']):.2f}",
                f"{ATTR_VOLTAGE}_per_battery": f"{voltage_per_battery:.2f}",
            }
        else:
            self._attr_extra_state_attributes = {}


class Felaqua(SurePetcareEntity, SensorEntity):
    """Sure Petcare Felaqua."""

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS

    def __init__(
        self, surepetcare_id: int, coordinator: SurePetcareDataCoordinator
    ) -> None:
        """Initialize a Sure Petcare Felaqua sensor."""
        super().__init__(surepetcare_id, coordinator)

        surepy_entity = cast(SurepyFelaqua, coordinator.data[surepetcare_id])

        self._attr_name = self._device_name
        self._attr_unique_id = self._device_id
        self._attr_entity_picture = surepy_entity.icon

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Update the state."""
        surepy_entity = cast(SurepyFelaqua, surepy_entity)
        self._attr_native_value = surepy_entity.water_remaining


class PetLastSeenFlapDevice(SurePetcareEntity, SensorEntity):
    """Sensor for the last flap device id used by the pet.

    Note: Will be unknown if the last status is not from a flap update.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, surepetcare_id: int, coordinator: SurePetcareDataCoordinator
    ) -> None:
        """Initialize last seen flap device id sensor."""
        super().__init__(surepetcare_id, coordinator)

        self._attr_name = f"{self._device_name} Last seen flap device id"
        self._attr_unique_id = f"{self._device_id}-last_seen_flap_device"

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        surepy_entity = cast(SurepyPet, surepy_entity)
        position = surepy_entity._data.get("position", {})  # noqa: SLF001
        device_id = position.get("device_id")
        self._attr_native_value = str(device_id) if device_id is not None else None


class PetLastSeenUser(SurePetcareEntity, SensorEntity):
    """Sensor for the last user id that manually changed the pet location.

    Note: Will be unknown if the last status is not from a manual update.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, surepetcare_id: int, coordinator: SurePetcareDataCoordinator
    ) -> None:
        """Initialize last seen user id sensor."""
        super().__init__(surepetcare_id, coordinator)

        self._attr_name = f"{self._device_name} Last seen user id"
        self._attr_unique_id = f"{self._device_id}-last_seen_user"

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        surepy_entity = cast(SurepyPet, surepy_entity)
        position = surepy_entity._data.get("position", {})  # noqa: SLF001
        user_id = position.get("user_id")
        self._attr_native_value = str(user_id) if user_id is not None else None
