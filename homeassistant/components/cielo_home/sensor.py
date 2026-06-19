"""Support for Cielo Home sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from cieloconnectapi.device import CieloDeviceAPI
from cieloconnectapi.model import CieloDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SENSOR_HUMIDITY, SENSOR_TEMPERATURE
from .coordinator import CieloDataUpdateCoordinator, CieloHomeConfigEntry
from .entity import CieloDeviceEntity, normalize_temp_unit


@dataclass(kw_only=True, frozen=True)
class CieloSensorEntityDescription(SensorEntityDescription):
    """Describes a Cielo Home sensor entity."""

    value_fn: Callable[[CieloDeviceAPI, CieloDevice | None], float | int | None]
    unit_fn: Callable[[CieloDeviceAPI, CieloDevice | None], str | None] | None = None


SENSOR_DESCRIPTIONS: tuple[CieloSensorEntityDescription, ...] = (
    CieloSensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda client, device_data: client.current_temperature(),
        # Temperature unit is dynamic; see the native_unit_of_measurement property for limitations.
        unit_fn=normalize_temp_unit,
    ),
    CieloSensorEntityDescription(
        key=SENSOR_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda client, device_data: (
            device_data.humidity if device_data else None
        ),
    ),
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CieloHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cielo Home sensors."""
    coordinator = entry.runtime_data

    entities = [
        CieloSensor(coordinator, device_id, description)
        for device_id in coordinator.data.parsed
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class CieloSensor(CieloDeviceEntity, SensorEntity):
    """Representation of a Cielo Home sensor."""

    entity_description: CieloSensorEntityDescription

    def __init__(
        self,
        coordinator: CieloDataUpdateCoordinator,
        device_id: str,
        entity_description: CieloSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def native_value(self) -> float | int | None:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.client, self.device_data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement.

        Note: The temperature unit is dynamic and can change based on device
        settings. If a user changes the device's temperature unit, historical
        statistics may be affected as the same numeric value will be interpreted
        differently. This is a known limitation of the device's API.
        """
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.client, self.device_data)
        return super().native_unit_of_measurement
