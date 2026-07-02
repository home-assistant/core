"""Sensor for the Theben Conexa Smartmeter gateway integration."""

import logging
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OBIS_IN, OBIS_OUT
from .coordinator import SmgwSensorCoordinator, ThebenConfigEntry
from .entity import ConexaSMGWEntity

_LOGGER = logging.getLogger(__name__)

# So far the Conexa 3.0 provides only total power in and out.
KNOWN_OBIS_CODES: dict[str, SensorEntityDescription] = {
    OBIS_IN: SensorEntityDescription(
        key=OBIS_IN,
        translation_key="power_consumed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    OBIS_OUT: SensorEntityDescription(
        key=OBIS_OUT,
        translation_key="power_supplied",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThebenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    sensors: list[TotalInOutSensor] = []

    for obis_code in entry.runtime_data.data:
        if obis_code in KNOWN_OBIS_CODES:
            sensors.append(
                TotalInOutSensor(
                    description=KNOWN_OBIS_CODES[obis_code],
                    coordinator=entry.runtime_data,
                )
            )
        else:
            _LOGGER.warning(
                "Skipping unsupported Conexa SMGW key %s during setup", obis_code
            )

    async_add_entities(sensors)


class TotalInOutSensor(ConexaSMGWEntity, SensorEntity):
    """Represents total Meter readings."""

    def __init__(
        self,
        description: SensorEntityDescription,
        coordinator: SmgwSensorCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._key = description.key
        # As far as I know the Conexa 3.0 returns always Wh but there is the possibility that it returns Joules
        if coordinator.data[self._key].unit.upper() == "J":
            self._attr_native_unit_of_measurement = UnitOfEnergy.JOULE
        self._attr_unique_id = (
            f"{coordinator.gateway_info.smgwID}-{coordinator.smgw_user}-{self._key}"
        )

    @property
    @override
    def native_value(self) -> str:
        """Return the current sensor value."""
        return self.coordinator.data[self._key].value
