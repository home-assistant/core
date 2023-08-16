"""Support for EufyLife sensors."""
from __future__ import annotations

from typing import Any

from eufylife_ble_client import MODEL_TO_NAME

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_address_present
<<<<<<< HEAD
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfMass
=======
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfMass,
)
>>>>>>> dde6ce6a996 (Add unit tests)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
<<<<<<< HEAD
=======
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.unit_conversion import MassConverter
>>>>>>> dde6ce6a996 (Add unit tests)
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

    _attr_translation_key = "real_time_weight"
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


<<<<<<< HEAD
class EufyLifeWeightSensorEntity(RestoreSensor, EufyLifeSensorEntity):
=======
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class EufyLifeWeightSensorEntity(RestoreEntity, EufyLifeSensorEntity):
>>>>>>> dde6ce6a996 (Add unit tests)
    """Representation of an EufyLife weight sensor."""

    _attr_translation_key = "weight"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_device_class = SensorDeviceClass.WEIGHT

<<<<<<< HEAD
=======
    _weight_kg: float | None = None

>>>>>>> dde6ce6a996 (Add unit tests)
    def __init__(self, data: EufyLifeData) -> None:
        """Initialize the weight sensor entity."""
        super().__init__(data)
        self._attr_unique_id = f"{data.address}_weight"

    @property
    def available(self) -> bool:
        """Determine if the entity is available."""
        return True

    @property
<<<<<<< HEAD
=======
    def native_value(self) -> float | None:
        """Return the native value."""
        return self._weight_kg

    @property
>>>>>>> dde6ce6a996 (Add unit tests)
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
<<<<<<< HEAD
            self._attr_native_value = state.final_weight_kg
=======
            self._weight_kg = state.final_weight_kg
>>>>>>> dde6ce6a996 (Add unit tests)

        super()._handle_state_update(args)

    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
<<<<<<< HEAD
        last_sensor_data = await self.async_get_last_sensor_data()

        if not last_state or not last_sensor_data or last_state.state in IGNORED_STATES:
            return

        self._attr_native_value = last_sensor_data.native_value


class EufyLifeHeartRateSensorEntity(RestoreSensor, EufyLifeSensorEntity):
=======
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


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class EufyLifeHeartRateSensorEntity(RestoreEntity, EufyLifeSensorEntity):
>>>>>>> dde6ce6a996 (Add unit tests)
    """Representation of an EufyLife heart rate sensor."""

    _attr_translation_key = "heart_rate"
    _attr_icon = "mdi:heart-pulse"
    _attr_native_unit_of_measurement = "bpm"

<<<<<<< HEAD
=======
    _heart_rate: int | None = None

>>>>>>> dde6ce6a996 (Add unit tests)
    def __init__(self, data: EufyLifeData) -> None:
        """Initialize the heart rate sensor entity."""
        super().__init__(data)
        self._attr_unique_id = f"{data.address}_heart_rate"

    @property
    def available(self) -> bool:
        """Determine if the entity is available."""
        return True

<<<<<<< HEAD
=======
    @property
    def native_value(self) -> float | None:
        """Return the native value."""
        return self._heart_rate

>>>>>>> dde6ce6a996 (Add unit tests)
    @callback
    def _handle_state_update(self, *args: Any) -> None:
        """Handle state update."""
        state = self._data.client.state
        if state is not None and state.heart_rate is not None:
<<<<<<< HEAD
            self._attr_native_value = state.heart_rate
=======
            self._heart_rate = state.heart_rate
>>>>>>> dde6ce6a996 (Add unit tests)

        super()._handle_state_update(args)

    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
<<<<<<< HEAD
        last_sensor_data = await self.async_get_last_sensor_data()

        if not last_state or not last_sensor_data or last_state.state in IGNORED_STATES:
            return

        self._attr_native_value = last_sensor_data.native_value
=======
        if not last_state or last_state.state in IGNORED_STATES:
            return

        self._heart_rate = int(last_state.state)
>>>>>>> dde6ce6a996 (Add unit tests)
