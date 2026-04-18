"""Support for Satel Integra temperature sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ENABLE_TEMPERATURE_SENSOR, CONF_ZONE_NUMBER, SUBENTRY_TYPE_ZONE
from .coordinator import SatelConfigEntry, SatelIntegraTemperaturesCoordinator
from .entity import SatelIntegraEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Satel Integra temperature sensors."""
    runtime_data = config_entry.runtime_data

    temperature_subentries = filter(
        lambda subentry: subentry.data.get(CONF_ENABLE_TEMPERATURE_SENSOR, False),
        config_entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE),
    )

    for subentry in temperature_subentries:
        zone_num: int = subentry.data[CONF_ZONE_NUMBER]

        async_add_entities(
            [
                SatelIntegraTemperatureSensor(
                    runtime_data.coordinator_temperatures,
                    config_entry.entry_id,
                    subentry,
                    zone_num,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraTemperatureSensor(
    SatelIntegraEntity[SatelIntegraTemperaturesCoordinator], SensorEntity
):
    """Representation of a Satel Integra temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "temperature"

    def __init__(
        self,
        coordinator: SatelIntegraTemperaturesCoordinator,
        config_entry_id: str,
        subentry: ConfigSubentry,
        device_number: int,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(
            coordinator,
            config_entry_id,
            subentry,
            device_number,
        )

        self._attr_native_value = self._get_state_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._get_state_from_coordinator()
        self.async_write_ha_state()

    def _get_state_from_coordinator(self) -> float | None:
        """Get temperature from coordinator data."""
        return self.coordinator.data.get(self._device_number)
