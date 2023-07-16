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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONDITIONS_MAP,
    DATA,
    DOMAIN,
    SENSOR_DATA_CATEGORY_GEOFENCE,
    SENSOR_DATA_CATEGORY_WEATHER,
    SIGNAL_TADO_UPDATE_RECEIVED,
    TYPE_AIR_CONDITIONING,
    TYPE_HEATING,
    TYPE_HOT_WATER,
)
from .entity import TadoHomeEntity, TadoZoneEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class TadoSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    state_fn: Callable[[Any], StateType]


@dataclass
class TadoSensorEntityDescription(
    SensorEntityDescription, TadoSensorEntityDescriptionMixin
):
    """Describes Tado sensor entity."""

    attributes_fn: Callable[[Any], dict[Any, StateType]] | None = None
    data_category: str | None = None


HOME_SENSORS = [
    TadoSensorEntityDescription(
        key="outdoor temperature",
        name="Outdoor temperature",
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
        name="Solar percentage",
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
        name="Weather condition",
        state_fn=lambda data: format_condition(data["weatherState"]["value"]),
        attributes_fn=lambda data: {"time": data["weatherState"]["timestamp"]},
        data_category=SENSOR_DATA_CATEGORY_WEATHER,
    ),
    TadoSensorEntityDescription(
        key="tado mode",
        name="Tado mode",
        # pylint: disable=unnecessary-lambda
        state_fn=lambda data: get_tado_mode(data),
        data_category=SENSOR_DATA_CATEGORY_GEOFENCE,
    ),
    TadoSensorEntityDescription(
        key="geofencing mode",
        name="Geofencing mode",
        # pylint: disable=unnecessary-lambda
        state_fn=lambda data: get_geofencing_mode(data),
        data_category=SENSOR_DATA_CATEGORY_GEOFENCE,
    ),
    TadoSensorEntityDescription(
        key="automatic geofencing",
        name="Automatic geofencing",
        # pylint: disable=unnecessary-lambda
        state_fn=lambda data: get_automatic_geofencing(data),
        data_category=SENSOR_DATA_CATEGORY_GEOFENCE,
    ),
]

TEMPERATURE_ENTITY_DESCRIPTION = TadoSensorEntityDescription(
    key="temperature",
    name="Temperature",
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
    name="Humidity",
    state_fn=lambda data: data.current_humidity,
    attributes_fn=lambda data: {"time": data.current_humidity_timestamp},
    native_unit_of_measurement=PERCENTAGE,
    device_class=SensorDeviceClass.HUMIDITY,
    state_class=SensorStateClass.MEASUREMENT,
)
TADO_MODE_ENTITY_DESCRIPTION = TadoSensorEntityDescription(
    key="tado mode",
    name="Tado mode",
    state_fn=lambda data: data.tado_mode,
)
HEATING_ENTITY_DESCRIPTION = TadoSensorEntityDescription(
    key="heating",
    name="Heating",
    state_fn=lambda data: data.heating_power_percentage,
    attributes_fn=lambda data: {"time": data.heating_power_timestamp},
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
)
AC_ENTITY_DESCRIPTION = TadoSensorEntityDescription(
    key="ac",
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


def format_condition(condition: str) -> str:
    """Return condition from dict CONDITIONS_MAP."""
    for key, value in CONDITIONS_MAP.items():
        if condition in value:
            return key
    return condition


def get_tado_mode(data) -> str | None:
    """Return Tado Mode based on Presence attribute."""
    if "presence" in data:
        return data["presence"]
    return None


def get_automatic_geofencing(data) -> bool:
    """Return whether Automatic Geofencing is enabled based on Presence Locked attribute."""
    if "presenceLocked" in data:
        if data["presenceLocked"]:
            return False
        return True
    return False


def get_geofencing_mode(data) -> str:
    """Return Geofencing Mode based on Presence and Presence Locked attributes."""
    tado_mode = ""
    tado_mode = data.get("presence", "unknown")

    geofencing_switch_mode = ""
    if "presenceLocked" in data:
        if data["presenceLocked"]:
            geofencing_switch_mode = "manual"
        else:
            geofencing_switch_mode = "auto"
    else:
        geofencing_switch_mode = "manual"

    return f"{tado_mode.capitalize()} ({geofencing_switch_mode.capitalize()})"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tado sensor platform."""

    tado = hass.data[DOMAIN][entry.entry_id][DATA]
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

    _attr_has_entity_name = True

    def __init__(self, tado, entity_description: TadoSensorEntityDescription) -> None:
        """Initialize of the Tado Sensor."""
        self.entity_description = entity_description
        super().__init__(tado)
        self._tado = tado

        self._attr_unique_id = f"{entity_description.key} {tado.home_id}"

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(self._tado.home_id, "home", "data"),
                self._async_update_callback,
            )
        )
        self._async_update_home_data()

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_home_data()
        self.async_write_ha_state()

    @callback
    def _async_update_home_data(self):
        """Handle update callbacks."""
        try:
            tado_weather_data = self._tado.data["weather"]
            tado_geofence_data = self._tado.data["geofence"]
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


class TadoZoneSensor(TadoZoneEntity, SensorEntity):
    """Representation of a tado Sensor."""

    entity_description: TadoSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        tado,
        zone_name,
        zone_id,
        entity_description: TadoSensorEntityDescription,
    ) -> None:
        """Initialize of the Tado Sensor."""
        self.entity_description = entity_description
        self._tado = tado
        super().__init__(zone_name, tado.home_id, zone_id)

        self._attr_unique_id = f"{entity_description.key} {zone_id} {tado.home_id}"

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "zone", self.zone_id
                ),
                self._async_update_callback,
            )
        )
        self._async_update_zone_data()

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_zone_data()
        self.async_write_ha_state()

    @callback
    def _async_update_zone_data(self):
        """Handle update callbacks."""
        try:
            tado_zone_data = self._tado.data["zone"][self.zone_id]
        except KeyError:
            return

        self._attr_native_value = self.entity_description.state_fn(tado_zone_data)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                tado_zone_data
            )
