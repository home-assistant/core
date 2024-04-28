"""Support for the Netatmo sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

import pyatmo
from pyatmo.modules import PublicWeatherArea

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
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    async_entries_for_config_entry,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_URL_ENERGY,
    CONF_URL_PUBLIC_WEATHER,
    CONF_WEATHER_AREAS,
    DATA_HANDLER,
    DOMAIN,
    NETATMO_CREATE_BATTERY,
    NETATMO_CREATE_ROOM_SENSOR,
    NETATMO_CREATE_SENSOR,
    NETATMO_CREATE_WEATHER_SENSOR,
    SIGNAL_NAME,
)
from .data_handler import HOME, PUBLIC, NetatmoDataHandler, NetatmoDevice, NetatmoRoom
from .entity import (
    NetatmoBaseEntity,
    NetatmoModuleEntity,
    NetatmoRoomEntity,
    NetatmoWeatherModuleEntity,
)
from .helper import NetatmoArea

_LOGGER = logging.getLogger(__name__)

DIRECTION_OPTIONS = [
    "n",
    "ne",
    "e",
    "se",
    "s",
    "sw",
    "w",
    "nw",
]


def process_health(health: StateType) -> str | None:
    """Process health index and return string for display."""
    if not isinstance(health, int):
        return None
    return {
        0: "healthy",
        1: "fine",
        2: "fair",
        3: "poor",
    }.get(health, "unhealthy")


def process_rf(strength: StateType) -> str | None:
    """Process wifi signal strength and return string for display."""
    if not isinstance(strength, int):
        return None
    if strength >= 90:
        return "Low"
    if strength >= 76:
        return "Medium"
    if strength >= 60:
        return "High"
    return "Full"


def process_wifi(strength: StateType) -> str | None:
    """Process wifi signal strength and return string for display."""
    if not isinstance(strength, int):
        return None
    if strength >= 86:
        return "Low"
    if strength >= 71:
        return "Medium"
    if strength >= 56:
        return "High"
    return "Full"


@dataclass(frozen=True, kw_only=True)
class NetatmoSensorEntityDescription(SensorEntityDescription):
    """Describes Netatmo sensor entity."""

    netatmo_name: str
    value_fn: Callable[[StateType], StateType] = lambda x: x


SENSOR_TYPES: tuple[NetatmoSensorEntityDescription, ...] = (
    NetatmoSensorEntityDescription(
        key="temperature",
        netatmo_name="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
    ),
    NetatmoSensorEntityDescription(
        key="temp_trend",
        netatmo_name="temp_trend",
        entity_registry_enabled_default=False,
    ),
    NetatmoSensorEntityDescription(
        key="co2",
        netatmo_name="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO2,
    ),
    NetatmoSensorEntityDescription(
        key="pressure",
        netatmo_name="pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        suggested_display_precision=1,
    ),
    NetatmoSensorEntityDescription(
        key="pressure_trend",
        netatmo_name="pressure_trend",
        entity_registry_enabled_default=False,
    ),
    NetatmoSensorEntityDescription(
        key="noise",
        netatmo_name="noise",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="humidity",
        netatmo_name="humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    NetatmoSensorEntityDescription(
        key="rain",
        netatmo_name="rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_1",
        netatmo_name="sum_rain_1",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_24",
        netatmo_name="sum_rain_24",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    NetatmoSensorEntityDescription(
        key="battery_percent",
        netatmo_name="battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
    NetatmoSensorEntityDescription(
        key="windangle",
        netatmo_name="wind_direction",
        device_class=SensorDeviceClass.ENUM,
        options=DIRECTION_OPTIONS,
        value_fn=lambda x: x.lower() if isinstance(x, str) else None,
    ),
    NetatmoSensorEntityDescription(
        key="windangle_value",
        netatmo_name="wind_angle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="windstrength",
        netatmo_name="wind_strength",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="gustangle",
        netatmo_name="gust_direction",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=DIRECTION_OPTIONS,
        value_fn=lambda x: x.lower() if isinstance(x, str) else None,
    ),
    NetatmoSensorEntityDescription(
        key="gustangle_value",
        netatmo_name="gust_angle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="guststrength",
        netatmo_name="gust_strength",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="reachable",
        netatmo_name="reachable",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NetatmoSensorEntityDescription(
        key="rf_status",
        netatmo_name="rf_strength",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=process_rf,
    ),
    NetatmoSensorEntityDescription(
        key="wifi_status",
        netatmo_name="wifi_strength",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=process_wifi,
    ),
    NetatmoSensorEntityDescription(
        key="health_idx",
        netatmo_name="health_idx",
        device_class=SensorDeviceClass.ENUM,
        options=["healthy", "fine", "fair", "poor", "unhealthy"],
        value_fn=process_health,
    ),
    NetatmoSensorEntityDescription(
        key="power",
        netatmo_name="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
)
SENSOR_TYPES_KEYS = [desc.key for desc in SENSOR_TYPES]


@dataclass(frozen=True, kw_only=True)
class NetatmoPublicWeatherSensorEntityDescription(SensorEntityDescription):
    """Describes Netatmo sensor entity."""

    value_fn: Callable[[PublicWeatherArea], dict[str, Any]]


PUBLIC_WEATHER_STATION_TYPES: tuple[
    NetatmoPublicWeatherSensorEntityDescription, ...
] = (
    NetatmoPublicWeatherSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        value_fn=lambda area: area.get_latest_temperatures(),
    ),
    NetatmoPublicWeatherSensorEntityDescription(
        key="pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        suggested_display_precision=1,
        value_fn=lambda area: area.get_latest_pressures(),
    ),
    NetatmoPublicWeatherSensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
        value_fn=lambda area: area.get_latest_humidities(),
    ),
    NetatmoPublicWeatherSensorEntityDescription(
        key="rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda area: area.get_latest_rain(),
    ),
    NetatmoPublicWeatherSensorEntityDescription(
        key="sum_rain_1",
        translation_key="sum_rain_1",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=lambda area: area.get_60_min_rain(),
    ),
    NetatmoPublicWeatherSensorEntityDescription(
        key="sum_rain_24",
        translation_key="sum_rain_24",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda area: area.get_24_h_rain(),
    ),
    NetatmoPublicWeatherSensorEntityDescription(
        key="windangle_value",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda area: area.get_latest_wind_angles(),
    ),
    NetatmoPublicWeatherSensorEntityDescription(
        key="windstrength",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda area: area.get_latest_wind_strengths(),
    ),
    NetatmoPublicWeatherSensorEntityDescription(
        key="gustangle_value",
        translation_key="gust_angle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda area: area.get_latest_gust_angles(),
    ),
    NetatmoPublicWeatherSensorEntityDescription(
        key="guststrength",
        translation_key="gust_strength",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda area: area.get_latest_gust_strengths(),
    ),
)

BATTERY_SENSOR_DESCRIPTION = NetatmoSensorEntityDescription(
    key="battery",
    netatmo_name="battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    device_class=SensorDeviceClass.BATTERY,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo sensor platform."""

    @callback
    def _create_battery_entity(netatmo_device: NetatmoDevice) -> None:
        if not hasattr(netatmo_device.device, "battery"):
            return
        entity = NetatmoClimateBatterySensor(netatmo_device)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_BATTERY, _create_battery_entity)
    )

    @callback
    def _create_weather_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoWeatherSensor(netatmo_device, description)
            for description in SENSOR_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_WEATHER_SENSOR, _create_weather_sensor_entity
        )
    )

    @callback
    def _create_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        _LOGGER.debug(
            "Adding %s sensor %s",
            netatmo_device.device.device_category,
            netatmo_device.device.name,
        )
        async_add_entities(
            NetatmoSensor(netatmo_device, description)
            for description in SENSOR_TYPES
            if description.key in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_SENSOR, _create_sensor_entity)
    )

    @callback
    def _create_room_sensor_entity(netatmo_device: NetatmoRoom) -> None:
        if not netatmo_device.room.climate_type:
            msg = f"No climate type found for this room: {netatmo_device.room.name}"
            _LOGGER.debug(msg)
            return
        async_add_entities(
            NetatmoRoomSensor(netatmo_device, description)
            for description in SENSOR_TYPES
            if description.key in netatmo_device.room.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_ROOM_SENSOR, _create_room_sensor_entity
        )
    )

    device_registry = dr.async_get(hass)
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    async def add_public_entities(update: bool = True) -> None:
        """Retrieve Netatmo public weather entities."""
        entities = {
            device.name: device.id
            for device in async_entries_for_config_entry(
                device_registry, entry.entry_id
            )
            if device.model == "Public Weather station"
        }

        new_entities: list[NetatmoPublicSensor] = []
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
                NetatmoPublicSensor(data_handler, area, description)
                for description in PUBLIC_WEATHER_STATION_TYPES
            )

        for device_id in entities.values():
            device_registry.async_remove_device(device_id)

        async_add_entities(new_entities)

    async_dispatcher_connect(
        hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}", add_public_entities
    )

    await add_public_entities(False)


class NetatmoWeatherSensor(NetatmoWeatherModuleEntity, SensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device)
        self.entity_description = description
        self._attr_translation_key = description.netatmo_name
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.device.reachable
            or getattr(self.device, self.entity_description.netatmo_name) is not None
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        value = cast(
            StateType, getattr(self.device, self.entity_description.netatmo_name)
        )
        if value is not None:
            value = self.entity_description.value_fn(value)
        self._attr_native_value = value
        self.async_write_ha_state()


class NetatmoClimateBatterySensor(NetatmoModuleEntity, SensorEntity):
    """Implementation of a Netatmo sensor."""

    entity_description: NetatmoSensorEntityDescription
    device: pyatmo.modules.NRV
    _attr_configuration_url = CONF_URL_ENERGY

    def __init__(self, netatmo_device: NetatmoDevice) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device)
        self.entity_description = BATTERY_SENSOR_DESCRIPTION

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: netatmo_device.signal_name,
                },
            ]
        )

        self._attr_unique_id = f"{netatmo_device.parent_id}-{self.device.entity_id}-{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, netatmo_device.parent_id)},
            name=netatmo_device.device.name,
            manufacturer=self.device_description[0],
            model=self.device_description[1],
            configuration_url=self._attr_configuration_url,
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self.device.reachable:
            if self.available:
                self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = self.device.battery


class NetatmoSensor(NetatmoModuleEntity, SensorEntity):
    """Implementation of a Netatmo sensor."""

    entity_description: NetatmoSensorEntityDescription
    _attr_configuration_url = CONF_URL_ENERGY

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device)
        self.entity_description = description

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: netatmo_device.signal_name,
                },
            ]
        )

        self._attr_unique_id = (
            f"{self.device.entity_id}-{self.device.entity_id}-{description.key}"
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self.device.reachable:
            if self.available:
                self._attr_available = False
            return

        if (state := getattr(self.device, self.entity_description.key)) is None:
            return

        self._attr_available = True
        self._attr_native_value = state

        self.async_write_ha_state()


class NetatmoRoomSensor(NetatmoRoomEntity, SensorEntity):
    """Implementation of a Netatmo room sensor."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_room: NetatmoRoom,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_room)
        self.entity_description = description

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: netatmo_room.signal_name,
                },
            ]
        )

        self._attr_unique_id = (
            f"{self.device.entity_id}-{self.device.entity_id}-{description.key}"
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if (state := getattr(self.device, self.entity_description.key)) is None:
            return

        self._attr_native_value = state

        self.async_write_ha_state()


class NetatmoPublicSensor(NetatmoBaseEntity, SensorEntity):
    """Represent a single sensor in a Netatmo."""

    entity_description: NetatmoPublicWeatherSensorEntityDescription

    def __init__(
        self,
        data_handler: NetatmoDataHandler,
        area: NetatmoArea,
        description: NetatmoPublicWeatherSensorEntityDescription,
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
        self._show_on_map = area.show_on_map
        self._attr_unique_id = f"{area.area_name.replace(' ', '-')}-{description.key}"

        self._attr_extra_state_attributes.update(
            {
                ATTR_LATITUDE: (area.lat_ne + area.lat_sw) / 2,
                ATTR_LONGITUDE: (area.lon_ne + area.lon_sw) / 2,
            }
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, area.area_name)},
            name=area.area_name,
            model="Public Weather station",
            manufacturer="Netatmo",
            configuration_url=CONF_URL_PUBLIC_WEATHER,
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"netatmo-config-{self.area.area_name}",
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
        data = self.entity_description.value_fn(self._station)

        if not data:
            if self.available:
                _LOGGER.error(
                    "No station provides %s data in the area %s",
                    self.entity_description.key,
                    self.area.area_name,
                )

            self._attr_available = False
            return

        if values := [x for x in data.values() if x is not None]:
            if self._mode == "avg":
                self._attr_native_value = round(sum(values) / len(values), 1)
            elif self._mode == "max":
                self._attr_native_value = max(values)

        self._attr_available = self.native_value is not None
        self.async_write_ha_state()
