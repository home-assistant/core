"""Sensor platform for healthbox."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, MANUFACTURER, HealthboxRoom
from .coordinator import HealthboxDataUpdateCoordinator


@dataclass
class HealthboxGlobalEntityDescriptionMixin:
    """Mixin values for Healthbox Global entities."""

    value_fn: Callable[[], float | int | str | Decimal | None]


@dataclass
class HealthboxGlobalSensorEntityDescription(
    SensorEntityDescription, HealthboxGlobalEntityDescriptionMixin
):
    """Class describing Healthbox Global sensor entities."""


@dataclass
class HealthboxRoomEntityDescriptionMixin:
    """Mixin values for Healthbox Room entities."""

    room: HealthboxRoom
    value_fn: Callable[[], float | int | str | Decimal | None]


@dataclass
class HealthboxRoomSensorEntityDescription(
    SensorEntityDescription, HealthboxRoomEntityDescriptionMixin
):
    """Class describing Healthbox Room sensor entities."""


def generate_room_sensors_for_healthbox(
    coordinator: HealthboxDataUpdateCoordinator,
) -> list[HealthboxRoomSensorEntityDescription]:
    """Generate sensors for each room."""
    room_sensors: list[HealthboxRoomSensorEntityDescription] = []
    if coordinator.api.advanced_api_enabled:
        for room in coordinator.api.rooms:
            if "indoor temperature" in room.enabled_sensors:
                room_sensors.append(
                    HealthboxRoomSensorEntityDescription(
                        key=f"{room.room_id}_temperature",
                        name=f"{room.name} Temperature",
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        icon="mdi:thermometer",
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        room=room,
                        value_fn=lambda x: x.indoor_temperature,
                        suggested_display_precision=2,
                    ),
                )
            if "indoor relative humidity" in room.enabled_sensors:
                room_sensors.append(
                    HealthboxRoomSensorEntityDescription(
                        key=f"{room.room_id}_humidity",
                        name=f"{room.name} Humidity",
                        native_unit_of_measurement=PERCENTAGE,
                        icon="mdi:water-percent",
                        device_class=SensorDeviceClass.HUMIDITY,
                        state_class=SensorStateClass.MEASUREMENT,
                        room=room,
                        value_fn=lambda x: x.indoor_humidity,
                        suggested_display_precision=2,
                    ),
                )
            if "indoor CO2" in room.enabled_sensors:
                if room.indoor_co2_concentration is not None:
                    room_sensors.append(
                        HealthboxRoomSensorEntityDescription(
                            key=f"{room.room_id}_co2_concentration",
                            name=f"{room.name} CO2 Concentration",
                            native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                            icon="mdi:molecule-co2",
                            device_class=SensorDeviceClass.CO2,
                            state_class=SensorStateClass.MEASUREMENT,
                            room=room,
                            value_fn=lambda x: x.indoor_co2_concentration,
                            suggested_display_precision=2,
                        ),
                    )
            if "indoor air quality index" in room.enabled_sensors:
                if room.indoor_aqi is not None:
                    room_sensors.append(
                        HealthboxRoomSensorEntityDescription(
                            key=f"{room.room_id}_aqi",
                            name=f"{room.name} Air Quality Index",
                            native_unit_of_measurement=None,
                            icon="mdi:leaf",
                            device_class=SensorDeviceClass.AQI,
                            state_class=SensorStateClass.MEASUREMENT,
                            room=room,
                            value_fn=lambda x: x.indoor_aqi,
                            suggested_display_precision=2,
                        ),
                    )
            if "indoor volatile organic compounds" in room.enabled_sensors:
                if room.indoor_voc_microg_per_cubic is not None:
                    room_sensors.append(
                        HealthboxRoomSensorEntityDescription(
                            key=f"{room.room_id}_voc",
                            name=f"{room.name} Volatile Organic Compounds",
                            native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                            icon="mdi:leaf",
                            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
                            state_class=SensorStateClass.MEASUREMENT,
                            room=room,
                            value_fn=lambda x: x.indoor_voc_microg_per_cubic,
                            suggested_display_precision=2,
                        ),
                    )

    for room in coordinator.api.rooms:
        if room.boost is not None:
            room_sensors.append(
                HealthboxRoomSensorEntityDescription(
                    key=f"{room.room_id}_boost_level",
                    name=f"{room.name} Boost Level",
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:fan",
                    # device_class=SensorDeviceClass.,
                    state_class=SensorStateClass.MEASUREMENT,
                    room=room,
                    value_fn=lambda x: x.boost.level,
                    suggested_display_precision=2,
                ),
            )
        if room.airflow_ventilation_rate is not None:
            room_sensors.append(
                HealthboxRoomSensorEntityDescription(
                    key=f"{room.room_id}_airflow_ventilation_rate",
                    name=f"{room.name} Airflow Ventilation Rate",
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:fan",
                    # device_class=SensorDeviceClass.,
                    state_class=SensorStateClass.MEASUREMENT,
                    room=room,
                    value_fn=lambda x: x.airflow_ventilation_rate * 100,
                    suggested_display_precision=2,
                ),
            )
        if room.profile_name is not None:
            room_sensors.append(
                HealthboxRoomSensorEntityDescription(
                    key=f"{room.room_id}_profile",
                    name=f"{room.name} Profile",
                    icon="mdi:account-box",
                    room=room,
                    value_fn=lambda x: x.profile_name,
                ),
            )
    return room_sensors


def generate_global_sensors_for_healthbox(
    coordinator: HealthboxDataUpdateCoordinator,
) -> list[HealthboxGlobalSensorEntityDescription]:
    """Generate global sensors."""
    global_sensors: list[HealthboxGlobalSensorEntityDescription] = []
    global_sensors.append(
        HealthboxGlobalSensorEntityDescription(
            key="global_aqi",
            name="Global Air Quality Index",
            native_unit_of_measurement=None,
            icon="mdi:leaf",
            device_class=SensorDeviceClass.AQI,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda x: x.global_aqi,
            suggested_display_precision=2,
        )
    )
    global_sensors.append(
        HealthboxGlobalSensorEntityDescription(
            key="error_count",
            name="Error Count",
            native_unit_of_measurement=None,
            icon="mdi:alert-outline",
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda x: x.error_count,
            suggested_display_precision=0,
        )
    )
    if coordinator.api.wifi.status:
        global_sensors.append(
            HealthboxGlobalSensorEntityDescription(
                key="wifi_status",
                name="WiFi Status",
                icon="mdi:wifi",
                value_fn=lambda x: x.wifi.status,
            )
        )
    if coordinator.api.wifi.internet_connection is not None:
        global_sensors.append(
            HealthboxGlobalSensorEntityDescription(
                key="wifi_internet_connection",
                name="WiFi Internet Connection",
                native_unit_of_measurement=None,
                icon="mdi:web",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda x: x.wifi.internet_connection,
            )
        )
    if coordinator.api.wifi.ssid:
        global_sensors.append(
            HealthboxGlobalSensorEntityDescription(
                key="wifi_ssid",
                name="WiFi SSID",
                icon="mdi:wifi-settings",
                value_fn=lambda x: x.wifi.ssid,
            )
        )
    return global_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: HealthboxDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    global_sensors = generate_global_sensors_for_healthbox(coordinator=coordinator)
    room_sensors = generate_room_sensors_for_healthbox(coordinator=coordinator)
    entities = []

    for description in global_sensors:
        entities.append(HealthboxGlobalSensor(coordinator, description))
    for description in room_sensors:
        entities.append(HealthboxRoomSensor(coordinator, description))

    async_add_entities(entities)


class HealthboxGlobalSensor(
    CoordinatorEntity[HealthboxDataUpdateCoordinator], SensorEntity
):
    """Representation of a Healthbox  Room Sensor."""

    entity_description: HealthboxGlobalSensorEntityDescription

    def __init__(
        self,
        coordinator: HealthboxDataUpdateCoordinator,
        description: HealthboxGlobalSensorEntityDescription,
    ) -> None:
        """Initialize Sensor Domain."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self._attr_name = f"Healthbox {description.name}"
        self._attr_device_info = DeviceInfo(
            name=f"{coordinator.api.serial}",
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=coordinator.api.description,
            hw_version=coordinator.api.warranty_number,
            sw_version=coordinator.api.firmware_version,
        )

    @property
    def native_value(self) -> float | int | str | Decimal:
        """Sensor native value."""
        return self.entity_description.value_fn(self.coordinator.api)


class HealthboxRoomSensor(
    CoordinatorEntity[HealthboxDataUpdateCoordinator], SensorEntity
):
    """Representation of a Healthbox Room Sensor."""

    entity_description: HealthboxRoomSensorEntityDescription

    def __init__(
        self,
        coordinator: HealthboxDataUpdateCoordinator,
        description: HealthboxRoomSensorEntityDescription,
    ) -> None:
        """Initialize Sensor Domain."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.room.room_id}-{description.key}"
        self._attr_name = f"{description.name}"
        self._attr_device_info = DeviceInfo(
            name=self.entity_description.room.name,
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.config_entry.unique_id}_{self.entity_description.room.room_id}",
                )
            },
            manufacturer="Renson",
            model="Healthbox Room",
        )

    @property
    def native_value(self) -> float | int | str | Decimal:
        """Sensor native value."""
        room_id: int = int(self.entity_description.room.room_id)

        matching_room = [
            room for room in self.coordinator.api.rooms if int(room.room_id) == room_id
        ]

        if len(matching_room) != 1:
            error_msg: str = f"No matching room found for id {room_id}"
            LOGGER.error(error_msg)
        else:
            matching_room = matching_room[0]
            return self.entity_description.value_fn(matching_room)

        return None
