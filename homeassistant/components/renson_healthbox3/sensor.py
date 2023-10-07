"""Sensor data of the Renson ventilation unit."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RensonCoordinator
from .entity import RensonEntity


class HealthboxRoomBoost:
    """Healthbox  Room Boost object."""

    level: float
    enabled: bool
    remaining: int

    def __init__(
        self, level: float = 100, enabled: bool = False, remaining: int = 900
    ) -> None:
        """Initialize the HB Room Boost."""
        self.level = level
        self.enabled = enabled
        self.remaining = remaining


class HealthboxRoom:
    """Healthbox  Room object."""

    boost: HealthboxRoomBoost

    def __init__(self, room_id: int, room_data: dict[str, Any]) -> None:
        """Initialize the HB Room."""
        self.room_id: int = room_id
        self.name: str = room_data["name"]
        self.type: str = room_data["type"]
        self.sensors_data: list = room_data["sensor"]
        self.room_type: str = room_data["type"]

    @property
    def indoor_temperature(self) -> Decimal:
        """HB Indoor Temperature."""
        return [
            sensor["parameter"]["temperature"]["value"]
            for sensor in self.sensors_data
            if "temperature" in sensor["parameter"]
        ][0]

    @property
    def indoor_humidity(self) -> Decimal:
        """HB Indoor Humidity."""
        return [
            sensor["parameter"]["humidity"]["value"]
            for sensor in self.sensors_data
            if "humidity" in sensor["parameter"]
        ][0]

    @property
    def indoor_co2_concentration(self) -> Decimal | None:
        """HB Indoor CO2 Concentration."""
        co2_concentration = None
        try:
            co2_concentration = [
                sensor["parameter"]["concentration"]["value"]
                for sensor in self.sensors_data
                if "concentration" in sensor["parameter"]
            ][0]
        except IndexError:
            co2_concentration = None
        return co2_concentration

    @property
    def indoor_aqi(self) -> Decimal | None:
        """HB Indoor Air Quality Index."""
        aqi = None
        try:
            aqi = [
                sensor["parameter"]["index"]["value"]
                for sensor in self.sensors_data
                if "index" in sensor["parameter"]
            ][0]
        except IndexError:
            aqi = None
        return aqi


@dataclass
class HealthboxGlobalEntityDescriptionMixin:
    """Mixin values for Healthbox Global entities."""

    value_fn: Callable[[Any], Any]


@dataclass
class HealthboxGlobalSensorEntityDescription(
    SensorEntityDescription, HealthboxGlobalEntityDescriptionMixin
):
    """Class describing Healthbox Global sensor entities."""


@dataclass
class HealthboxRoomEntityDescriptionMixin:
    """Mixin values for Healthbox Room entities."""

    room: HealthboxRoom
    value_fn: Callable[[Any], Any]


@dataclass
class HealthboxRoomSensorEntityDescription(
    SensorEntityDescription, HealthboxRoomEntityDescriptionMixin
):
    """Class describing Healthbox Room sensor entities."""


HEALTHBOX_GLOBAL_SENSORS: tuple[HealthboxGlobalSensorEntityDescription, ...] = (
    HealthboxGlobalSensorEntityDescription(
        key="global_aqi",
        name="Global Air Quality Index",
        icon="mdi:leaf",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.global_aqi,
        suggested_display_precision=2,
    ),
    HealthboxGlobalSensorEntityDescription(
        key="error_count",
        name="Error Count",
        icon="mdi:alert-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.error_count,
        suggested_display_precision=0,
    ),
    HealthboxGlobalSensorEntityDescription(
        key="wifi_status",
        name="Wi-Fi Status",
        icon="mdi:wifi",
        value_fn=lambda x: x.wifi.status,
    ),
    HealthboxGlobalSensorEntityDescription(
        key="wifi_internet_connection",
        name="Wi-Fi Internet Connection",
        icon="mdi:web",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.wifi.internet_connection,
    ),
    HealthboxGlobalSensorEntityDescription(
        key="wifi_ssid",
        name="Wi-Fi SSID",
        icon="mdi:wifi-settings",
        value_fn=lambda x: x.wifi.ssid,
    ),
)


def generate_room_sensors_for_healthbox(
    coordinator: RensonCoordinator,
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


class HealthboxGlobalSensor(RensonEntity, SensorEntity):
    """Representation of a Healthbox  Room Sensor."""

    entity_description: HealthboxGlobalSensorEntityDescription

    def __init__(
        self,
        coordinator: RensonCoordinator,
        description: HealthboxGlobalSensorEntityDescription,
    ) -> None:
        """Initialize Sensor Domain."""
        super().__init__(description.key, coordinator)

        self.entity_description = description
        self._attr_name = f"Healthbox {description.name}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._attr_native_value = self.entity_description.value_fn(self.coordinator.api)

        self.async_write_ha_state()


class HealthboxRoomSensor(RensonEntity, SensorEntity):
    """Representation of a Healthbox Room Sensor."""

    entity_description: HealthboxRoomSensorEntityDescription

    def __init__(
        self,
        coordinator: RensonCoordinator,
        description: HealthboxRoomSensorEntityDescription,
    ) -> None:
        """Initialize Sensor Domain."""
        super().__init__(description.key, coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.room.room_id}-{description.key}"
        self._attr_name = f"{description.name}"
        self._attr_device_info = DeviceInfo(
            name=self.entity_description.room.name,
            identifiers={
                (
                    DOMAIN,
                    f"{DOMAIN}_{self.entity_description.room.room_id}",
                )
            },
            manufacturer="Renson",
            model="Healthbox Room",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        room_id: int = int(self.entity_description.room.room_id)

        matching_room = [
            room for room in self.coordinator.api.rooms if int(room.room_id) == room_id
        ]

        if len(matching_room) != 1:
            pass
        else:
            matching_room = matching_room[0]
            self._attr_native_value = self.entity_description.value_fn(matching_room)

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson sensor platform."""

    coordinator: RensonCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[RensonEntity] = []

    entities = [
        HealthboxGlobalSensor(coordinator, description)
        for description in HEALTHBOX_GLOBAL_SENSORS
    ]

    room_sensors = generate_room_sensors_for_healthbox(coordinator=coordinator)

    for description in room_sensors:
        entities.append(HealthboxRoomSensor(coordinator, description))

    async_add_entities(entities)
