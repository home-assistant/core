"""Support for EufyLife sensors."""
from __future__ import annotations

from typing import Any

from eufylife_ble_client import MODEL_TO_NAME

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_address_present
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.unit_conversion import MassConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import DOMAIN
from .models import EufyLifeData

IGNORED_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EufyLife sensors."""
    data: EufyLifeData = hass.data[DOMAIN][entry.entry_id]

    entities = [
        EufyLifeWeightSensorEntity(data),
        EufyLifeRealTimeWeightSensorEntity(data),
    ]

    if data.client.supports_heart_rate:
        entities.append(EufyLifeHeartRateSensorEntity(data))

    async_add_entities(entities)


class EufyLifeSensorEntity(SensorEntity):
    """Representation of an EufyLife sensor."""

    _attr_has_entity_name = True

    def __init__(self, data: EufyLifeData) -> None:
        """Initialize the weight sensor entity."""
        self._data = data

        self._attr_device_info = DeviceInfo(
            name=MODEL_TO_NAME[data.model],
            connections={(dr.CONNECTION_BLUETOOTH, data.address)},
        )

    @property
    def available(self) -> bool:
        """Determine if the entity is available."""
        if self._data.client.advertisement_data_contains_state:
            # If the device only uses advertisement data, just check if the address is present.
            return async_address_present(self.hass, self._data.address)

        # If the device needs an active connection, availability is based on whether it is connected.
        return self._data.client.is_connected

    @callback
    def _handle_state_update(self, *args: Any) -> None:
        """Handle state update."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback."""
        self.async_on_remove(
            self._data.client.register_callback(self._handle_state_update)
        )


class EufyLifeRealTimeWeightSensorEntity(EufyLifeSensorEntity):
    """Representation of an EufyLife real-time weight sensor."""

    _attr_name = "Real-time weight"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_device_class = SensorDeviceClass.WEIGHT

    def __init__(self, data: EufyLifeData) -> None:
        """Initialize the real-time weight sensor entity."""
        super().__init__(data)
        self._attr_unique_id = f"{data.address}_real_time_weight"

    @property
    def native_value(self) -> float | None:
        """Return the native value."""
        if self._data.client.state is not None:
            return self._data.client.state.weight_kg
        return None

    @property
    def suggested_unit_of_measurement(self) -> str | None:
        """Set the suggested unit based on the unit system."""
        if self.hass.config.units is US_CUSTOMARY_SYSTEM:
            return UnitOfMass.POUNDS

        return UnitOfMass.KILOGRAMS


class EufyLifeWeightSensorEntity(RestoreEntity, EufyLifeSensorEntity):
    """Representation of an EufyLife weight sensor."""

    _attr_name = "Weight"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_device_class = SensorDeviceClass.WEIGHT

    _weight_kg: float | None = None

    def __init__(self, data: EufyLifeData) -> None:
        """Initialize the weight sensor entity."""
        super().__init__(data)
        self._attr_unique_id = f"{data.address}_weight"

    @property
    def available(self) -> bool:
        """Determine if the entity is available."""
        return True

    @property
    def native_value(self) -> float | None:
        """Return the native value."""
        return self._weight_kg

    @property
    def suggested_unit_of_measurement(self) -> str | None:
        """Set the suggested unit based on the unit system."""
        if self.hass.config.units is US_CUSTOMARY_SYSTEM:
            return UnitOfMass.POUNDS

        return UnitOfMass.KILOGRAMS

    @callback
    def _handle_state_update(self, *args: Any) -> None:
        """Handle state update."""
        state = self._data.client.state
        if state is not None and state.final_weight_kg is not None:
            self._weight_kg = state.final_weight_kg

        super()._handle_state_update(args)

    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if not last_state or last_state.state in IGNORED_STATES:
            return

        last_weight = float(last_state.state)
        last_weight_unit = last_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        # Since the RestoreEntity stores the state using the displayed unit,
        # not the native unit, we need to convert the state back to the native
        # unit.
        self._weight_kg = MassConverter.convert(
            last_weight, last_weight_unit, self.native_unit_of_measurement
        )


class EufyLifeHeartRateSensorEntity(RestoreEntity, EufyLifeSensorEntity):
    """Representation of an EufyLife heart rate sensor."""

    _attr_name = "Heart rate"
    _attr_icon = "mdi:heart-pulse"
    _attr_native_unit_of_measurement = "bpm"

    _heart_rate: int | None = None

    def __init__(self, data: EufyLifeData) -> None:
        """Initialize the heart rate sensor entity."""
        super().__init__(data)
        self._attr_unique_id = f"{data.address}_heart_rate"

    @property
    def available(self) -> bool:
        """Determine if the entity is available."""
        return True

    @property
    def native_value(self) -> float | None:
        """Return the native value."""
        return self._heart_rate

    @callback
    def _handle_state_update(self, *args: Any) -> None:
        """Handle state update."""
        state = self._data.client.state
        if state is not None and state.heart_rate is not None:
            self._heart_rate = state.heart_rate

        super()._handle_state_update(args)

    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if not last_state or last_state.state in IGNORED_STATES:
            return

        self._heart_rate = int(last_state.state)
