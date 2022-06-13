"""Support for the Netatmo sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import cast

import pyatmo

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
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_MBAR,
    SOUND_PRESSURE_DB,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_entries_for_config_entry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_URL_ENERGY,
    CONF_URL_WEATHER,
    CONF_WEATHER_AREAS,
    DATA_HANDLER,
    DOMAIN,
    NETATMO_CREATE_BATTERY,
    NETATMO_CREATE_ROOM_SENSOR,
    NETATMO_CREATE_WEATHER_SENSOR,
    SIGNAL_NAME,
)
from .data_handler import HOME, PUBLIC, NetatmoDataHandler, NetatmoDevice, NetatmoRoom
from .helper import NetatmoArea
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)

SUPPORTED_PUBLIC_SENSOR_TYPES: tuple[str, ...] = (
    "temperature",
    "pressure",
    "humidity",
    "rain",
    "wind_strength",
    "gust_strength",
    "sum_rain_1",
    "sum_rain_24",
    "wind_angle",
    "gust_angle",
)


@dataclass
class NetatmoSensorEntityDescription(SensorEntityDescription):
    """Describes Netatmo sensor entity."""


SENSOR_TYPES: tuple[NetatmoSensorEntityDescription, ...] = (
    NetatmoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    NetatmoSensorEntityDescription(
        key="temp_trend",
        name="Temperature trend",
        entity_registry_enabled_default=False,
        icon="mdi:trending-up",
    ),
    NetatmoSensorEntityDescription(
        key="co2",
        name="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO2,
    ),
    NetatmoSensorEntityDescription(
        key="pressure",
        name="Pressure",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=PRESSURE_MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    NetatmoSensorEntityDescription(
        key="pressure_trend",
        name="Pressure trend",
        entity_registry_enabled_default=False,
        icon="mdi:trending-up",
    ),
    NetatmoSensorEntityDescription(
        key="noise",
        name="Noise",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=SOUND_PRESSURE_DB,
        icon="mdi:volume-high",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="humidity",
        name="Humidity",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    NetatmoSensorEntityDescription(
        key="rain",
        name="Rain",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-rainy",
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_1",
        name="Rain last hour",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:weather-rainy",
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_24",
        name="Rain today",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:weather-rainy",
    ),
    NetatmoSensorEntityDescription(
        key="battery",
        name="Battery Percent",
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
    NetatmoSensorEntityDescription(
        key="wind_direction",
        name="Direction",
        entity_registry_enabled_default=True,
        icon="mdi:compass-outline",
    ),
    NetatmoSensorEntityDescription(
        key="wind_angle",
        name="Angle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="wind_strength",
        name="Wind Strength",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="gust_direction",
        name="Gust Direction",
        entity_registry_enabled_default=False,
        icon="mdi:compass-outline",
    ),
    NetatmoSensorEntityDescription(
        key="gust_angle",
        name="Gust Angle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="gust_strength",
        name="Gust Strength",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="reachable",
        name="Reachability",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:signal",
    ),
    NetatmoSensorEntityDescription(
        key="rf_strength",
        name="Radio",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:signal",
    ),
    NetatmoSensorEntityDescription(
        key="wifi_strength",
        name="Wifi",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:wifi",
    ),
    NetatmoSensorEntityDescription(
        key="health_idx",
        name="Health",
        entity_registry_enabled_default=True,
        icon="mdi:cloud",
    ),
    NetatmoSensorEntityDescription(
        key="power",
        name="Power",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.POWER,
    ),
)
SENSOR_TYPES_KEYS = [desc.key for desc in SENSOR_TYPES]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo sensor platform."""

    @callback
    def _create_battery_entity(netatmo_device: NetatmoDevice) -> None:
        if not hasattr(netatmo_device.device, "battery"):
            return
        entity = NetatmoClimateBatterySensor(netatmo_device)
        _LOGGER.debug("Adding climate battery sensor %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_BATTERY, _create_battery_entity)
    )

    @callback
    def _create_weather_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        _LOGGER.debug(
            "Adding %s sensor %s",
            netatmo_device.device.device_category,
            netatmo_device.device.name,
        )
        async_add_entities(
            [
                NetatmoWeatherSensor(netatmo_device, description)
                for description in SENSOR_TYPES
                if description.key in netatmo_device.device.features
            ]
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_WEATHER_SENSOR, _create_weather_sensor_entity
        )
    )

    @callback
    def _create_room_sensor_entity(netatmo_device: NetatmoRoom) -> None:
        _LOGGER.debug("Adding %s sensor", netatmo_device.room.name)
        async_add_entities(
            [
                NetatmoRoomSensor(netatmo_device, description)
                for description in SENSOR_TYPES
                if description.key in netatmo_device.room.features
            ]
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_ROOM_SENSOR, _create_room_sensor_entity
        )
    )

    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]
    device_registry = await hass.helpers.device_registry.async_get_registry()

    async def add_public_entities(update: bool = True) -> None:
        """Retrieve Netatmo public weather entities."""
        entities = {
            device.name: device.id
            for device in async_entries_for_config_entry(
                device_registry, entry.entry_id
            )
            if device.model == "Public Weather station"
        }

        new_entities = []
        for area in [
            NetatmoArea(**i) for i in entry.options.get(CONF_WEATHER_AREAS, {}).values()
        ]:
            signal_name = f"{PUBLIC}-{area.uuid}"

            if area.area_name in entities:
                entities.pop(area.area_name)

                if update:
                    async_dispatcher_send(
                        hass,
                        f"netatmo-config-{area.area_name}",
                        area,
                    )
                    continue

            await data_handler.subscribe(
                PUBLIC,
                signal_name,
                None,
                lat_ne=area.lat_ne,
                lon_ne=area.lon_ne,
                lat_sw=area.lat_sw,
                lon_sw=area.lon_sw,
                area_id=str(area.uuid),
            )

            new_entities.extend(
                [
                    NetatmoPublicSensor(data_handler, area, description)
                    for description in SENSOR_TYPES
                    if description.key in SUPPORTED_PUBLIC_SENSOR_TYPES
                ]
            )

        for device_id in entities.values():
            device_registry.async_remove_device(device_id)

        if new_entities:
            async_add_entities(new_entities)

    async_dispatcher_connect(
        hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}", add_public_entities
    )

    await add_public_entities(False)


class NetatmoWeatherSensor(NetatmoBase, SensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = description

        self._module = netatmo_device.device
        self._id = self._module.entity_id
        self._station_id = (
            self._module.bridge if self._module.bridge is not None else self._id
        )
        self._device_name = self._module.name
        category = getattr(self._module.device_category, "name")
        self._publishers.extend(
            [
                {
                    "name": category,
                    SIGNAL_NAME: category,
                },
            ]
        )

        self._attr_name = f"{self._device_name} {description.name}"
        self._model = self._module.device_type
        self._config_url = CONF_URL_WEATHER
        self._attr_unique_id = f"{self._id}-{description.key}"

        if hasattr(self._module, "place"):
            place = cast(
                pyatmo.modules.base_class.Place, getattr(self._module, "place")
            )
            if hasattr(place, "location") and place.location is not None:
                self._attr_extra_state_attributes.update(
                    {
                        ATTR_LATITUDE: place.location.latitude,
                        ATTR_LONGITUDE: place.location.longitude,
                    }
                )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.state is not None

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        try:
            if (state := getattr(self._module, self.entity_description.key)) is None:
                return

            if self.entity_description.key in {"temperature", "pressure", "sum_rain_1"}:
                self._attr_native_value = round(state, 1)
            elif self.entity_description.key == "rf_strength":
                self._attr_native_value = process_rf(state)
            elif self.entity_description.key == "wifi_strength":
                self._attr_native_value = process_wifi(state)
            elif self.entity_description.key == "health_idx":
                self._attr_native_value = process_health(state)
            else:
                self._attr_native_value = state
        except KeyError:
            if self.state:
                _LOGGER.debug(
                    "No %s data found for %s",
                    self.entity_description.key,
                    self._device_name,
                )
            self._attr_native_value = None
            return

        self.async_write_ha_state()


class NetatmoClimateBatterySensor(NetatmoBase, SensorEntity):
    """Implementation of a Netatmo sensor."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = NetatmoSensorEntityDescription(
            key="battery",
            name="Battery Percent",
            entity_registry_enabled_default=True,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.BATTERY,
        )

        self._module = cast(pyatmo.modules.NRV, netatmo_device.device)
        self._id = netatmo_device.parent_id

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: netatmo_device.signal_name,
                },
            ]
        )

        self._attr_name = f"{self._module.name} {self.entity_description.name}"
        self._room_id = self._module.room_id
        self._model = getattr(self._module.device_type, "value")
        self._config_url = CONF_URL_ENERGY

        self._attr_unique_id = (
            f"{self._id}-{self._module.entity_id}-{self.entity_description.key}"
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
                self._attr_native_value = None
            return

        self._attr_available = True
        self._attr_native_value = self._module.battery


def process_health(health: int) -> str:
    """Process health index and return string for display."""
    if health == 0:
        return "Healthy"
    if health == 1:
        return "Fine"
    if health == 2:
        return "Fair"
    if health == 3:
        return "Poor"
    return "Unhealthy"


def process_rf(strength: int) -> str:
    """Process wifi signal strength and return string for display."""
    if strength >= 90:
        return "Low"
    if strength >= 76:
        return "Medium"
    if strength >= 60:
        return "High"
    return "Full"


def process_wifi(strength: int) -> str:
    """Process wifi signal strength and return string for display."""
    if strength >= 86:
        return "Low"
    if strength >= 71:
        return "Medium"
    if strength >= 56:
        return "High"
    return "Full"


class NetatmoRoomSensor(NetatmoBase, SensorEntity):
    """Implementation of a Netatmo room sensor."""

    def __init__(
        self,
        netatmo_room: NetatmoRoom,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_room.data_handler)
        self.entity_description = description

        self._room = netatmo_room.room
        self._id = self._room.entity_id

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_room.room.home.entity_id,
                    SIGNAL_NAME: netatmo_room.signal_name,
                },
            ]
        )

        self._attr_name = f"{self._room.name} {self.entity_description.name}"
        self._room_id = self._room.entity_id
        self._model = f"{self._room.climate_type}"
        self._config_url = CONF_URL_ENERGY

        self._attr_unique_id = (
            f"{self._id}-{self._room.entity_id}-{self.entity_description.key}"
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        try:
            if (state := getattr(self._room, self.entity_description.key)) is None:
                return

            self._attr_native_value = state

        except KeyError:
            if self.state:
                _LOGGER.debug(
                    "No %s data found for %s",
                    self.entity_description.key,
                    self._device_name,
                )
            self._attr_native_value = None
            return

        self.async_write_ha_state()


class NetatmoPublicSensor(NetatmoBase, SensorEntity):
    """Represent a single sensor in a Netatmo."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        data_handler: NetatmoDataHandler,
        area: NetatmoArea,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data_handler)
        self.entity_description = description

        self._signal_name = f"{PUBLIC}-{area.uuid}"
        self._publishers.append(
            {
                "name": PUBLIC,
                "lat_ne": area.lat_ne,
                "lon_ne": area.lon_ne,
                "lat_sw": area.lat_sw,
                "lon_sw": area.lon_sw,
                "area_name": area.area_name,
                SIGNAL_NAME: self._signal_name,
            }
        )

        self._station = data_handler.account.public_weather_areas[str(area.uuid)]

        self.area = area
        self._mode = area.mode
        self._area_name = area.area_name
        self._id = self._area_name
        self._device_name = f"{self._area_name}"
        self._attr_name = f"{self._device_name} {description.name}"
        self._show_on_map = area.show_on_map
        self._attr_unique_id = (
            f"{self._device_name.replace(' ', '-')}-{description.key}"
        )
        self._model = PUBLIC

        self._attr_extra_state_attributes.update(
            {
                ATTR_LATITUDE: (self.area.lat_ne + self.area.lat_sw) / 2,
                ATTR_LONGITUDE: (self.area.lon_ne + self.area.lon_sw) / 2,
            }
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        assert self.device_info and "name" in self.device_info
        self.data_handler.config_entry.async_on_unload(
            async_dispatcher_connect(
                self.hass,
                f"netatmo-config-{self.device_info['name']}",
                self.async_config_update_callback,
            )
        )

    async def async_config_update_callback(self, area: NetatmoArea) -> None:
        """Update the entity's config."""
        if self.area == area:
            return

        await self.data_handler.unsubscribe(
            self._signal_name, self.async_update_callback
        )

        self.area = area
        self._signal_name = f"{PUBLIC}-{area.uuid}"
        self._mode = area.mode
        self._show_on_map = area.show_on_map
        await self.data_handler.subscribe(
            PUBLIC,
            self._signal_name,
            self.async_update_callback,
            lat_ne=area.lat_ne,
            lon_ne=area.lon_ne,
            lat_sw=area.lat_sw,
            lon_sw=area.lon_sw,
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        data = None

        if self.entity_description.key == "temperature":
            data = self._station.get_latest_temperatures()
        elif self.entity_description.key == "pressure":
            data = self._station.get_latest_pressures()
        elif self.entity_description.key == "humidity":
            data = self._station.get_latest_humidities()
        elif self.entity_description.key == "rain":
            data = self._station.get_latest_rain()
        elif self.entity_description.key == "sum_rain_1":
            data = self._station.get_60_min_rain()
        elif self.entity_description.key == "sum_rain_24":
            data = self._station.get_24_h_rain()
        elif self.entity_description.key == "wind_strength":
            data = self._station.get_latest_wind_strengths()
        elif self.entity_description.key == "gust_strength":
            data = self._station.get_latest_gust_strengths()
        elif self.entity_description.key == "wind_angle":
            data = self._station.get_latest_wind_angles()
        elif self.entity_description.key == "gust_angle":
            data = self._station.get_latest_gust_angles()

        if not data:
            if self.available:
                _LOGGER.error(
                    "No station provides %s data in the area %s",
                    self.entity_description.key,
                    self._area_name,
                )
                self._attr_native_value = None

            self._attr_available = False
            return

        if values := [x for x in data.values() if x is not None]:
            if self._mode == "avg":
                self._attr_native_value = round(sum(values) / len(values), 1)
            elif self._mode == "max":
                self._attr_native_value = max(values)

        self._attr_available = self.state is not None
        self.async_write_ha_state()
