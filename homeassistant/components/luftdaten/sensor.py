"""Support for Sensor.Community sensors."""
from __future__ import annotations

from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_SHOW_ON_MAP,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTR_SENSOR_ID, CONF_SENSOR_ID, DOMAIN

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure",
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure_at_sealevel",
        name="Pressure at sealevel",
        native_unit_of_measurement=UnitOfPressure.PA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="P1",
        name="PM10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="P2",
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Sensor.Community sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensorCommunitySensor(
            coordinator=coordinator,
            description=description,
            sensor_id=entry.data[CONF_SENSOR_ID],
            show_on_map=entry.data[CONF_SHOW_ON_MAP],
        )
        for description in SENSORS
        if description.key in coordinator.data
    )


class SensorCommunitySensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Sensor.Community sensor."""

    _attr_attribution = "Data provided by Sensor.Community"
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        *,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
        sensor_id: int,
        show_on_map: bool,
    ) -> None:
        """Initialize the Sensor.Community sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{sensor_id}_{description.key}"
        self._attr_extra_state_attributes = {
            ATTR_SENSOR_ID: sensor_id,
        }
        self._attr_device_info = DeviceInfo(
            configuration_url=(
                f"https://devices.sensor.community/sensors/{sensor_id}/settings"
            ),
            identifiers={(DOMAIN, str(sensor_id))},
            name=f"Sensor {sensor_id}",
            manufacturer="Sensor.Community",
        )

        if show_on_map:
            self._attr_extra_state_attributes[ATTR_LONGITUDE] = coordinator.data[
                "longitude"
            ]
            self._attr_extra_state_attributes[ATTR_LATITUDE] = coordinator.data[
                "latitude"
            ]

    @property
    def native_value(self) -> float | None:
        """Return the state of the device."""
        if (
            not self.coordinator.data
            or (value := self.coordinator.data.get(self.entity_description.key)) is None
        ):
            return None
        return cast(float, value)
