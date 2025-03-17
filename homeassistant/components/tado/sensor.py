"""Support for Tado sensors for each zone."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TadoConfigEntry
from .const import (
    CONDITIONS_MAP,
    SENSOR_DATA_CATEGORY_GEOFENCE,
    SENSOR_DATA_CATEGORY_WEATHER,
    TYPE_AIR_CONDITIONING,
    TYPE_HEATING,
    TYPE_HOT_WATER,
)
from .coordinator import TadoDataUpdateCoordinator
from .entity import TadoHomeEntity, TadoZoneEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TadoSensorEntityDescription(SensorEntityDescription):
    """Describes Tado sensor entity."""

    state_fn: Callable[[Any], StateType]

    attributes_fn: Callable[[Any], dict[Any, StateType]] | None = None
    data_category: str | None = None


def format_condition(condition: str) -> str:
    """Return condition from dict CONDITIONS_MAP."""
    for key, value in CONDITIONS_MAP.items():
        if condition in value:
            return key
    return condition


def get_tado_mode(data: dict[str, str]) -> str | None:
    """Return Tado Mode based on Presence attribute."""
    if "presence" in data:
        return data["presence"]
    return None


def get_automatic_geofencing(data: dict[str, str]) -> bool:
    """Return whether Automatic Geofencing is enabled based on Presence Locked attribute."""
    if "presenceLocked" in data:
        if data["presenceLocked"]:
            return False
        return True
    return False


def get_geofencing_mode(data: dict[str, str]) -> str:
    """Return Geofencing Mode based on Presence and Presence Locked attributes."""
    tado_mode = data.get("presence", "unknown")

    if "presenceLocked" in data:
        if data["presenceLocked"]:
            geofencing_switch_mode = "manual"
        else:
            geofencing_switch_mode = "auto"
    else:
        geofencing_switch_mode = "manual"

    return f"{tado_mode.capitalize()} ({geofencing_switch_mode.capitalize()})"


HOME_SENSORS = [
    TadoSensorEntityDescription(
        key="outdoor temperature",
        translation_key="outdoor_temperature",
        state_fn=lambda data: data["outsideTemperature"]["celsius"],
        attributes_fn=lambda data: {
            "time": data["outsideTemperature"]["timestamp"],
        },
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        data_category=SENSOR_DATA_CATEGORY_WEATHER,
    ),
    TadoSensorEntityDescription(
        key="solar percentage",
        translation_key="solar_percentage",
        state_fn=lambda data: data["solarIntensity"]["percentage"],
        attributes_fn=lambda data: {
            "time": data["solarIntensity"]["timestamp"],
        },
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        data_category=SENSOR_DATA_CATEGORY_WEATHER,
    ),
    TadoSensorEntityDescription(
        key="weather condition",
        translation_key="weather_condition",
        state_fn=lambda data: format_condition(data["weatherState"]["value"]),
        attributes_fn=lambda data: {"time": data["weatherState"]["timestamp"]},
        data_category=SENSOR_DATA_CATEGORY_WEATHER,
    ),
    TadoSensorEntityDescription(
        key="tado mode",
        translation_key="tado_mode",
        state_fn=get_tado_mode,
        data_category=SENSOR_DATA_CATEGORY_GEOFENCE,
    ),
    TadoSensorEntityDescription(
        key="geofencing mode",
        translation_key="geofencing_mode",
        state_fn=get_geofencing_mode,
        data_category=SENSOR_DATA_CATEGORY_GEOFENCE,
    ),
    TadoSensorEntityDescription(
        key="automatic geofencing",
        translation_key="automatic_geofencing",
        state_fn=get_automatic_geofencing,
        data_category=SENSOR_DATA_CATEGORY_GEOFENCE,
    ),
]

TEMPERATURE_ENTITY_DESCRIPTION = TadoSensorEntityDescription(
    key="temperature",
    state_fn=lambda data: data.current_temp,
    attributes_fn=lambda data: {
        "time": data.current_temp_timestamp,
        "setting": 0,  # setting is used in climate device
    },
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
)
HUMIDITY_ENTITY_DESCRIPTION = TadoSensorEntityDescription(
    key="humidity",
    state_fn=lambda data: data.current_humidity,
    attributes_fn=lambda data: {"time": data.current_humidity_timestamp},
    native_unit_of_measurement=PERCENTAGE,
    device_class=SensorDeviceClass.HUMIDITY,
    state_class=SensorStateClass.MEASUREMENT,
)
TADO_MODE_ENTITY_DESCRIPTION = TadoSensorEntityDescription(
    key="tado mode",
    translation_key="tado_mode",
    state_fn=lambda data: data.tado_mode,
)
HEATING_ENTITY_DESCRIPTION = TadoSensorEntityDescription(
    key="heating",
    translation_key="heating",
    state_fn=lambda data: data.heating_power_percentage,
    attributes_fn=lambda data: {"time": data.heating_power_timestamp},
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
)
AC_ENTITY_DESCRIPTION = TadoSensorEntityDescription(
    key="ac",
    translation_key="ac",
    name="AC",
    state_fn=lambda data: data.ac_power,
    attributes_fn=lambda data: {"time": data.ac_power_timestamp},
)

ZONE_SENSORS = {
    TYPE_HEATING: [
        TEMPERATURE_ENTITY_DESCRIPTION,
        HUMIDITY_ENTITY_DESCRIPTION,
        TADO_MODE_ENTITY_DESCRIPTION,
        HEATING_ENTITY_DESCRIPTION,
    ],
    TYPE_AIR_CONDITIONING: [
        TEMPERATURE_ENTITY_DESCRIPTION,
        HUMIDITY_ENTITY_DESCRIPTION,
        TADO_MODE_ENTITY_DESCRIPTION,
        AC_ENTITY_DESCRIPTION,
    ],
    TYPE_HOT_WATER: [TADO_MODE_ENTITY_DESCRIPTION],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado sensor platform."""

    tado = entry.runtime_data.coordinator
    zones = tado.zones
    entities: list[SensorEntity] = []

    # Create home sensors
    entities.extend(
        [
            TadoHomeSensor(tado, entity_description)
            for entity_description in HOME_SENSORS
        ]
    )

    # Create zone sensors
    for zone in zones:
        zone_type = zone["type"]
        if zone_type not in ZONE_SENSORS:
            _LOGGER.warning("Unknown zone type skipped: %s", zone_type)
            continue

        entities.extend(
            [
                TadoZoneSensor(tado, zone["name"], zone["id"], entity_description)
                for entity_description in ZONE_SENSORS[zone_type]
            ]
        )

    async_add_entities(entities, True)


class TadoHomeSensor(TadoHomeEntity, SensorEntity):
    """Representation of a Tado Sensor."""

    entity_description: TadoSensorEntityDescription

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        entity_description: TadoSensorEntityDescription,
    ) -> None:
        """Initialize of the Tado Sensor."""
        self.entity_description = entity_description
        super().__init__(coordinator)

        self._attr_unique_id = f"{entity_description.key} {coordinator.home_id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            tado_weather_data = self.coordinator.data["weather"]
            tado_geofence_data = self.coordinator.data["geofence"]
        except KeyError:
            return

        if self.entity_description.data_category is not None:
            if self.entity_description.data_category == SENSOR_DATA_CATEGORY_WEATHER:
                tado_sensor_data = tado_weather_data
            else:
                tado_sensor_data = tado_geofence_data
        self._attr_native_value = self.entity_description.state_fn(tado_sensor_data)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                tado_sensor_data
            )
        super()._handle_coordinator_update()


class TadoZoneSensor(TadoZoneEntity, SensorEntity):
    """Representation of a tado Sensor."""

    entity_description: TadoSensorEntityDescription

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        zone_name: str,
        zone_id: int,
        entity_description: TadoSensorEntityDescription,
    ) -> None:
        """Initialize of the Tado Sensor."""
        self.entity_description = entity_description
        super().__init__(zone_name, coordinator.home_id, zone_id, coordinator)

        self._attr_unique_id = (
            f"{entity_description.key} {zone_id} {coordinator.home_id}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            tado_zone_data = self.coordinator.data["zone"][self.zone_id]
        except KeyError:
            return

        self._attr_native_value = self.entity_description.state_fn(tado_zone_data)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                tado_zone_data
            )
        super()._handle_coordinator_update()
