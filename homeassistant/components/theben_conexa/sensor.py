"""Sensor for the Theben Conexa Smartmeter gateway integration."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OBIS_IN, OBIS_OUT
from .coordinator import SmgwSensorCoordinator, ThebenConfigEntry
from .entity import ConexaSMGWEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThebenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    sensors = []
    for key in entry.runtime_data.data:
        translation_key = TotalInOutSensor.derive_translation_key(key)
        if translation_key:
            sensors.append(TotalInOutSensor(key, translation_key, entry.runtime_data))
        else:
            _LOGGER.warning("Skipping unsupported Conexa SMGW key %s during setup", key)

    async_add_entities(sensors)


class TotalInOutSensor(ConexaSMGWEntity, SensorEntity):
    """Represents total Meter readings."""

    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @classmethod
    def derive_translation_key(cls, key: str) -> str | None:
        """So far the Conexa 3.0 provides only total power in and out.

        But this might change in the future so we check the key
        """
        if OBIS_IN in key:
            # This is the total power consumed channel, which has the OBIS code 1-0:1.8.0
            return "power_consumed"
        if OBIS_OUT in key:
            # This is the total power supplied channel, which has the OBIS code 1-0:2.8.0
            return "power_supplied"
        return None

    def __init__(
        self, key: str, translation_key: str, coordinator: SmgwSensorCoordinator
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)

        self._attr_translation_key = translation_key
        self._key = key
        self._attr_native_value = coordinator.data[key].value
        # As far as I know the Conexa 3.0 returns always Wh but there is the possibility that it returns Joules
        if coordinator.data[key].unit.upper() == "J":
            self._attr_native_unit_of_measurement = UnitOfEnergy.JOULE
        self._attr_unique_id = f"{coordinator.gateway_info.smgwID}-{key}"

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data[self._key].value
        self.async_write_ha_state()
