"""Support for the Netatmo sensors."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import cast

import pyatmo
from pyatmo import DeviceType

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

from .const import (
    CONF_URL_ENERGY,
    CONF_URL_PUBLIC_WEATHER,
    CONF_URL_WEATHER,
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
from .entity import NetatmoBaseEntity, NetatmoModuleEntity, NetatmoRoomEntity
from .helper import NetatmoArea

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


@dataclass(frozen=True, kw_only=True)
class NetatmoSensorEntityDescription(SensorEntityDescription):
    """Describes Netatmo sensor entity."""

    netatmo_name: str


SENSOR_TYPES: tuple[NetatmoSensorEntityDescription, ...] = (
    NetatmoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        netatmo_name="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    NetatmoSensorEntityDescription(
        key="temp_trend",
        name="Temperature trend",
        netatmo_name="temp_trend",
        entity_registry_enabled_default=False,
        icon="mdi:trending-up",
    ),
    NetatmoSensorEntityDescription(
        key="co2",
        name="CO2",
        netatmo_name="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO2,
    ),
    NetatmoSensorEntityDescription(
        key="pressure",
        name="Pressure",
        netatmo_name="pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    ),
    NetatmoSensorEntityDescription(
        key="pressure_trend",
        name="Pressure trend",
        netatmo_name="pressure_trend",
        entity_registry_enabled_default=False,
        icon="mdi:trending-up",
    ),
    NetatmoSensorEntityDescription(
        key="noise",
        name="Noise",
        netatmo_name="noise",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="humidity",
        name="Humidity",
        netatmo_name="humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    NetatmoSensorEntityDescription(
        key="rain",
        name="Rain",
        netatmo_name="rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_1",
        name="Rain last hour",
        netatmo_name="sum_rain_1",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_24",
        name="Rain today",
        netatmo_name="sum_rain_24",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    NetatmoSensorEntityDescription(
        key="battery_percent",
        name="Battery Percent",
        netatmo_name="battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
    NetatmoSensorEntityDescription(
        key="windangle",
        name="Direction",
        netatmo_name="wind_direction",
        icon="mdi:compass-outline",
    ),
    NetatmoSensorEntityDescription(
        key="windangle_value",
        name="Angle",
        netatmo_name="wind_angle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="windstrength",
        name="Wind Strength",
        netatmo_name="wind_strength",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="gustangle",
        name="Gust Direction",
        netatmo_name="gust_direction",
        entity_registry_enabled_default=False,
        icon="mdi:compass-outline",
    ),
    NetatmoSensorEntityDescription(
        key="gustangle_value",
        name="Gust Angle",
        netatmo_name="gust_angle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="guststrength",
        name="Gust Strength",
        netatmo_name="gust_strength",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="reachable",
        name="Reachability",
        netatmo_name="reachable",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:signal",
    ),
    NetatmoSensorEntityDescription(
        key="rf_status",
        name="Radio",
        netatmo_name="rf_strength",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:signal",
    ),
    NetatmoSensorEntityDescription(
        key="wifi_status",
        name="Wifi",
        netatmo_name="wifi_strength",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:wifi",
    ),
    NetatmoSensorEntityDescription(
        key="health_idx",
        name="Health",
        netatmo_name="health_idx",
        icon="mdi:cloud",
    ),
    NetatmoSensorEntityDescription(
        key="power",
        name="Power",
        netatmo_name="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
)
SENSOR_TYPES_KEYS = [desc.key for desc in SENSOR_TYPES]

BATTERY_SENSOR_DESCRIPTION = NetatmoSensorEntityDescription(
    key="battery",
    name="Battery Percent",
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
                    if description.netatmo_name in SUPPORTED_PUBLIC_SENSOR_TYPES
                ]
            )

        for device_id in entities.values():
            device_registry.async_remove_device(device_id)

        async_add_entities(new_entities)

    async_dispatcher_connect(
        hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}", add_public_entities
    )

    await add_public_entities(False)


class NetatmoWeatherSensor(NetatmoModuleEntity, SensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    entity_description: NetatmoSensorEntityDescription
    _attr_configuration_url = CONF_URL_WEATHER

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device)
        self.entity_description = description
        category = getattr(self.device.device_category, "name")
        self._publishers.extend(
            [
                {
                    "name": category,
                    SIGNAL_NAME: category,
                },
            ]
        )
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

        if hasattr(self.device, "place"):
            place = cast(pyatmo.modules.base_class.Place, getattr(self.device, "place"))
            if hasattr(place, "location") and place.location is not None:
                self._attr_extra_state_attributes.update(
                    {
                        ATTR_LATITUDE: place.location.latitude,
                        ATTR_LONGITUDE: place.location.longitude,
                    }
                )

    @property
    def device_type(self) -> DeviceType:
        """Return the Netatmo device type."""
        if "." not in self.device.device_type:
            return super().device_type
        return DeviceType(self.device.device_type.partition(".")[2])

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if (
            not self.device.reachable
            or (state := getattr(self.device, self.entity_description.netatmo_name))
            is None
        ):
            if self.available:
                self._attr_available = False
            return

        if self.entity_description.netatmo_name in {
            "temperature",
            "pressure",
            "sum_rain_1",
        }:
            self._attr_native_value = round(state, 1)
        elif self.entity_description.netatmo_name == "rf_strength":
            self._attr_native_value = process_rf(state)
        elif self.entity_description.netatmo_name == "wifi_strength":
            self._attr_native_value = process_wifi(state)
        elif self.entity_description.netatmo_name == "health_idx":
            self._attr_native_value = process_health(state)
        else:
            self._attr_native_value = state

        self._attr_available = True
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
        data = None

        if self.entity_description.netatmo_name == "temperature":
            data = self._station.get_latest_temperatures()
        elif self.entity_description.netatmo_name == "pressure":
            data = self._station.get_latest_pressures()
        elif self.entity_description.netatmo_name == "humidity":
            data = self._station.get_latest_humidities()
        elif self.entity_description.netatmo_name == "rain":
            data = self._station.get_latest_rain()
        elif self.entity_description.netatmo_name == "sum_rain_1":
            data = self._station.get_60_min_rain()
        elif self.entity_description.netatmo_name == "sum_rain_24":
            data = self._station.get_24_h_rain()
        elif self.entity_description.netatmo_name == "wind_strength":
            data = self._station.get_latest_wind_strengths()
        elif self.entity_description.netatmo_name == "gust_strength":
            data = self._station.get_latest_gust_strengths()
        elif self.entity_description.netatmo_name == "wind_angle":
            data = self._station.get_latest_wind_angles()
        elif self.entity_description.netatmo_name == "gust_angle":
            data = self._station.get_latest_gust_angles()

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

        self._attr_available = self.state is not None
        self.async_write_ha_state()
