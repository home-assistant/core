"""Support for the Netatmo Weather Service."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import cast

import pyatmo

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_MBAR,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    SOUND_PRESSURE_DB,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.device_registry import async_entries_for_config_entry
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_WEATHER_AREAS,
    DATA_HANDLER,
    DOMAIN,
    MANUFACTURER,
    MODULE_TYPE_THERM,
    MODULE_TYPE_VALVE,
    NETATMO_CREATE_BATTERY,
    SIGNAL_NAME,
    TYPE_ENERGY,
    TYPE_WEATHER,
)
from .data_handler import (
    HOMECOACH_DATA_CLASS_NAME,
    HOMEDATA_DATA_CLASS_NAME,
    HOMESTATUS_DATA_CLASS_NAME,
    PUBLICDATA_DATA_CLASS_NAME,
    WEATHERSTATION_DATA_CLASS_NAME,
    NetatmoDataHandler,
)
from .helper import NetatmoArea
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)

SUPPORTED_PUBLIC_SENSOR_TYPES: tuple[str, ...] = (
    "temperature",
    "pressure",
    "humidity",
    "rain",
    "windstrength",
    "guststrength",
    "sum_rain_1",
    "sum_rain_24",
)


@dataclass
class NetatmoRequiredKeysMixin:
    """Mixin for required keys."""

    netatmo_name: str


@dataclass
class NetatmoSensorEntityDescription(SensorEntityDescription, NetatmoRequiredKeysMixin):
    """Describes Netatmo sensor entity."""


SENSOR_TYPES: dict[str, NetatmoSensorEntityDescription] = {
    "temperature": NetatmoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        netatmo_name="Temperature",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "temp_trend": NetatmoSensorEntityDescription(
        key="temp_trend",
        name="Temperature trend",
        netatmo_name="temp_trend",
        entity_registry_enabled_default=False,
        icon="mdi:trending-up",
    ),
    "co2": NetatmoSensorEntityDescription(
        key="co2",
        name="CO2",
        netatmo_name="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        entity_registry_enabled_default=True,
        device_class=DEVICE_CLASS_CO2,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "pressure": NetatmoSensorEntityDescription(
        key="pressure",
        name="Pressure",
        netatmo_name="Pressure",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=PRESSURE_MBAR,
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "pressure_trend": NetatmoSensorEntityDescription(
        key="pressure_trend",
        name="Pressure trend",
        netatmo_name="pressure_trend",
        entity_registry_enabled_default=False,
        icon="mdi:trending-up",
    ),
    "noise": NetatmoSensorEntityDescription(
        key="noise",
        name="Noise",
        netatmo_name="Noise",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=SOUND_PRESSURE_DB,
        icon="mdi:volume-high",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "humidity": NetatmoSensorEntityDescription(
        key="humidity",
        name="Humidity",
        netatmo_name="Humidity",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "rain": NetatmoSensorEntityDescription(
        key="rain",
        name="Rain",
        netatmo_name="Rain",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:weather-rainy",
    ),
    "sum_rain_1": NetatmoSensorEntityDescription(
        key="sum_rain_1",
        name="Rain last hour",
        netatmo_name="sum_rain_1",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        icon="mdi:weather-rainy",
    ),
    "sum_rain_24": NetatmoSensorEntityDescription(
        key="sum_rain_24",
        name="Rain today",
        netatmo_name="sum_rain_24",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        icon="mdi:weather-rainy",
    ),
    "battery_percent": NetatmoSensorEntityDescription(
        key="battery_percent",
        name="Battery Percent",
        netatmo_name="battery_percent",
        entity_registry_enabled_default=True,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "windangle": NetatmoSensorEntityDescription(
        key="windangle",
        name="Direction",
        netatmo_name="WindAngle",
        entity_registry_enabled_default=True,
        icon="mdi:compass-outline",
    ),
    "windangle_value": NetatmoSensorEntityDescription(
        key="windangle_value",
        name="Angle",
        netatmo_name="WindAngle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "windstrength": NetatmoSensorEntityDescription(
        key="windstrength",
        name="Wind Strength",
        netatmo_name="WindStrength",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "gustangle": NetatmoSensorEntityDescription(
        key="gustangle",
        name="Gust Direction",
        netatmo_name="GustAngle",
        entity_registry_enabled_default=False,
        icon="mdi:compass-outline",
    ),
    "gustangle_value": NetatmoSensorEntityDescription(
        key="gustangle_value",
        name="Gust Angle",
        netatmo_name="GustAngle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "guststrength": NetatmoSensorEntityDescription(
        key="guststrength",
        name="Gust Strength",
        netatmo_name="GustStrength",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "reachable": NetatmoSensorEntityDescription(
        key="reachable",
        name="Reachability",
        netatmo_name="reachable",
        entity_registry_enabled_default=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        icon="mdi:signal",
    ),
    "rf_status": NetatmoSensorEntityDescription(
        key="rf_status",
        name="Radio",
        netatmo_name="rf_status",
        entity_registry_enabled_default=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        icon="mdi:signal",
    ),
    "rf_status_lvl": NetatmoSensorEntityDescription(
        key="rf_status_lvl",
        name="Radio Level",
        netatmo_name="rf_status",
        entity_registry_enabled_default=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "wifi_status": NetatmoSensorEntityDescription(
        key="wifi_status",
        name="Wifi",
        netatmo_name="wifi_status",
        entity_registry_enabled_default=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        icon="mdi:wifi",
    ),
    "wifi_status_lvl": NetatmoSensorEntityDescription(
        key="wifi_status_lvl",
        name="Wifi Level",
        netatmo_name="wifi_status",
        entity_registry_enabled_default=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "health_idx": NetatmoSensorEntityDescription(
        key="health_idx",
        name="Health",
        netatmo_name="health_idx",
        entity_registry_enabled_default=True,
        icon="mdi:cloud",
    ),
}
SENSOR_TYPES_KEYS = [desc.key for desc in SENSOR_TYPES.values()]

PUBLIC = "public"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Netatmo weather and homecoach platform."""
    data_handler = hass.data[DOMAIN][config_entry.entry_id][DATA_HANDLER]
    platform_not_ready = True

    async def find_entities(data_class_name: str) -> list:
        """Find all entities."""
        all_module_infos = {}
        data = data_handler.data

        if data_class_name not in data:
            return []

        if data[data_class_name] is None:
            return []

        data_class = data[data_class_name]

        for station_id in data_class.stations:
            for module_id in data_class.get_modules(station_id):
                all_module_infos[module_id] = data_class.get_module(module_id)

            all_module_infos[station_id] = data_class.get_station(station_id)

        entities = []
        for module in all_module_infos.values():
            if "_id" not in module:
                _LOGGER.debug("Skipping module %s", module.get("module_name"))
                continue

            conditions = [
                c.lower()
                for c in data_class.get_monitored_conditions(module_id=module["_id"])
                if c.lower() in SENSOR_TYPES_KEYS
            ]
            for condition in conditions:
                if f"{condition}_value" in SENSOR_TYPES_KEYS:
                    conditions.append(f"{condition}_value")
                elif f"{condition}_lvl" in SENSOR_TYPES_KEYS:
                    conditions.append(f"{condition}_lvl")

            entities.extend(
                [
                    NetatmoSensor(data_handler, data_class_name, module, description)
                    for description in SENSOR_TYPES.values()
                    if description.key in conditions
                ]
            )

        _LOGGER.debug("Adding weather sensors %s", entities)
        return entities

    for data_class_name in (
        WEATHERSTATION_DATA_CLASS_NAME,
        HOMECOACH_DATA_CLASS_NAME,
    ):
        await data_handler.register_data_class(data_class_name, data_class_name, None)
        data_class = data_handler.data.get(data_class_name)

        if data_class and data_class.raw_data:
            platform_not_ready = False

        async_add_entities(await find_entities(data_class_name), True)

    device_registry = await hass.helpers.device_registry.async_get_registry()

    async def add_public_entities(update: bool = True) -> None:
        """Retrieve Netatmo public weather entities."""
        entities = {
            device.name: device.id
            for device in async_entries_for_config_entry(
                device_registry, config_entry.entry_id
            )
            if device.model == "Public Weather stations"
        }

        new_entities = []
        for area in [
            NetatmoArea(**i)
            for i in config_entry.options.get(CONF_WEATHER_AREAS, {}).values()
        ]:
            signal_name = f"{PUBLICDATA_DATA_CLASS_NAME}-{area.uuid}"

            if area.area_name in entities:
                entities.pop(area.area_name)

                if update:
                    async_dispatcher_send(
                        hass,
                        f"netatmo-config-{area.area_name}",
                        area,
                    )
                    continue

            await data_handler.register_data_class(
                PUBLICDATA_DATA_CLASS_NAME,
                signal_name,
                None,
                lat_ne=area.lat_ne,
                lon_ne=area.lon_ne,
                lat_sw=area.lat_sw,
                lon_sw=area.lon_sw,
            )
            data_class = data_handler.data.get(signal_name)

            if data_class and data_class.raw_data:
                nonlocal platform_not_ready
                platform_not_ready = False

            new_entities.extend(
                [
                    NetatmoPublicSensor(data_handler, area, description)
                    for description in SENSOR_TYPES.values()
                    if description.key in SUPPORTED_PUBLIC_SENSOR_TYPES
                ]
            )

        for device_id in entities.values():
            device_registry.async_remove_device(device_id)

        if new_entities:
            async_add_entities(new_entities)

    async_dispatcher_connect(
        hass,
        f"signal-{DOMAIN}-public-update-{config_entry.entry_id}",
        add_public_entities,
    )

    async def _async_create_entity(
        data_handler: NetatmoDataHandler,
        home_status_class: str,
        home_id: str,
        room_id: str,
        device_name: str,
        model: str,
    ) -> None:
        entity = NetatmoClimateBatterySensor(
            data_handler, home_status_class, home_id, room_id, device_name, model
        )
        _LOGGER.debug("Adding climate battery sensor %s", entity)
        async_add_entities([entity])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_BATTERY, _async_create_entity)
    )

    await add_public_entities(False)

    if platform_not_ready:
        raise PlatformNotReady


class NetatmoClimateBatterySensor(NetatmoBase, SensorEntity):
    """Implementation of a Netatmo sensor."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        data_handler: NetatmoDataHandler,
        home_status_class: str,
        home_id: str,
        room_id: str,
        device_name: str,
        model: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data_handler)
        self.entity_description = SENSOR_TYPES["battery_percent"]

        self._id = room_id  # f"{home_id}-{room_id}"
        self._device_name = device_name
        self._home_status_class = home_status_class
        self._home_id = home_id
        self._room_id = room_id
        self._model = model

        self._data_classes.extend(
            [
                {
                    "name": HOMEDATA_DATA_CLASS_NAME,
                    SIGNAL_NAME: HOMEDATA_DATA_CLASS_NAME,
                },
                {
                    "name": HOMESTATUS_DATA_CLASS_NAME,
                    "home_id": self._home_id,
                    SIGNAL_NAME: self._home_status_class,
                },
            ]
        )

        self._home_status = self.data_handler.data[self._home_status_class]
        self._room_status = self._home_status.rooms[self._room_id]
        self._room_data: dict = self._data.rooms[home_id][room_id]

        self._attr_name = (
            f"{MANUFACTURER} {self._device_name} {self.entity_description.name}"
        )
        self._netatmo_type = TYPE_ENERGY
        self._attr_unique_id = f"{self._id}-{self.entity_description.key}"

    @property
    def _data(self) -> pyatmo.AsyncHomeData:
        """Return data for this entity."""
        return cast(
            pyatmo.AsyncHomeData, self.data_handler.data[self._data_classes[0]["name"]]
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._home_status = self.data_handler.data[self._home_status_class]
        if self._home_status is None:
            return

        self._room_status = self._home_status.rooms.get(self._room_id)
        self._room_data = self._data.rooms.get(self._home_id, {}).get(self._room_id, {})

        if not self._room_status or not self._room_data:
            return

        if self._room_status.get("reachable"):
            self._attr_native_value = self._process_battery_state()
        else:
            self._attr_native_value = None

    def _process_battery_state(self) -> int | None:
        """Construct room status."""
        try:
            m_id = self._room_data["module_ids"][0]
            batterylevel = None

            if self._model == MODULE_TYPE_THERM:
                batterylevel = self._home_status.thermostats[m_id].get("battery_state")
            elif self._model == MODULE_TYPE_VALVE:
                batterylevel = self._home_status.valves[m_id].get("battery_state")

            if batterylevel:
                return process_battery_percent(batterylevel)

        except KeyError as err:
            _LOGGER.error("Update of room %s failed. Error: %s", self._id, err)

        return None

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.state is not None


class NetatmoSensor(NetatmoBase, SensorEntity):
    """Implementation of a Netatmo sensor."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        data_handler: NetatmoDataHandler,
        data_class_name: str,
        module_info: dict,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data_handler)
        self.entity_description = description

        self._data_classes.append(
            {"name": data_class_name, SIGNAL_NAME: data_class_name}
        )

        self._id = module_info["_id"]
        self._station_id = module_info.get("main_device", self._id)

        station = self._data.get_station(self._station_id)
        if not (device := self._data.get_module(self._id)):
            # Assume it's a station if module can't be found
            device = station

        if device["type"] in ("NHC", "NAMain"):
            self._device_name = module_info["station_name"]
        else:
            self._device_name = (
                f"{station['station_name']} "
                f"{module_info.get('module_name', device['type'])}"
            )

        self._attr_name = f"{MANUFACTURER} {self._device_name} {description.name}"
        self._model = device["type"]
        self._netatmo_type = TYPE_WEATHER
        self._attr_unique_id = f"{self._id}-{description.key}"

    @property
    def _data(self) -> pyatmo.AsyncWeatherStationData:
        """Return data for this entity."""
        return cast(
            pyatmo.AsyncWeatherStationData,
            self.data_handler.data[self._data_classes[0]["name"]],
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.state is not None

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        data = self._data.get_last_data(station_id=self._station_id, exclude=3600).get(
            self._id
        )

        if data is None:
            if self.state:
                _LOGGER.debug(
                    "No data found for %s - %s (%s)",
                    self.name,
                    self._device_name,
                    self._id,
                )
            self._attr_native_value = None
            return

        try:
            state = data[self.entity_description.netatmo_name]
            if self.entity_description.key in {"temperature", "pressure", "sum_rain_1"}:
                self._attr_native_value = round(state, 1)
            elif self.entity_description.key in {"windangle_value", "gustangle_value"}:
                self._attr_native_value = fix_angle(state)
            elif self.entity_description.key in {"windangle", "gustangle"}:
                self._attr_native_value = process_angle(fix_angle(state))
            elif self.entity_description.key == "rf_status":
                self._attr_native_value = process_rf(state)
            elif self.entity_description.key == "wifi_status":
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


def fix_angle(angle: int) -> int:
    """Fix angle when value is negative."""
    if angle < 0:
        return 360 + angle
    return angle


def process_angle(angle: int) -> str:
    """Process angle and return string for display."""
    if angle >= 330:
        return "N"
    if angle >= 300:
        return "NW"
    if angle >= 240:
        return "W"
    if angle >= 210:
        return "SW"
    if angle >= 150:
        return "S"
    if angle >= 120:
        return "SE"
    if angle >= 60:
        return "E"
    if angle >= 30:
        return "NE"
    return "N"


def process_battery_percent(data: str) -> int:
    """Process battery data and return percent (int) for display."""
    mapping = {
        "max": 100,
        "full": 90,
        "high": 75,
        "medium": 50,
        "low": 25,
        "very low": 10,
    }
    return mapping[data]


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

        self._signal_name = f"{PUBLICDATA_DATA_CLASS_NAME}-{area.uuid}"

        self._data_classes.append(
            {
                "name": PUBLICDATA_DATA_CLASS_NAME,
                "lat_ne": area.lat_ne,
                "lon_ne": area.lon_ne,
                "lat_sw": area.lat_sw,
                "lon_sw": area.lon_sw,
                "area_name": area.area_name,
                SIGNAL_NAME: self._signal_name,
            }
        )

        self.area = area
        self._mode = area.mode
        self._area_name = area.area_name
        self._id = self._area_name
        self._device_name = f"{self._area_name}"
        self._attr_name = f"{MANUFACTURER} {self._device_name} {description.name}"
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

    @property
    def _data(self) -> pyatmo.AsyncPublicData:
        """Return data for this entity."""
        return cast(pyatmo.AsyncPublicData, self.data_handler.data[self._signal_name])

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

        await self.data_handler.unregister_data_class(
            self._signal_name, self.async_update_callback
        )

        self.area = area
        self._signal_name = f"{PUBLICDATA_DATA_CLASS_NAME}-{area.uuid}"
        self._data_classes = [
            {
                "name": PUBLICDATA_DATA_CLASS_NAME,
                "lat_ne": area.lat_ne,
                "lon_ne": area.lon_ne,
                "lat_sw": area.lat_sw,
                "lon_sw": area.lon_sw,
                "area_name": area.area_name,
                SIGNAL_NAME: self._signal_name,
            }
        ]
        self._mode = area.mode
        self._show_on_map = area.show_on_map
        await self.data_handler.register_data_class(
            PUBLICDATA_DATA_CLASS_NAME,
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
            data = self._data.get_latest_temperatures()
        elif self.entity_description.key == "pressure":
            data = self._data.get_latest_pressures()
        elif self.entity_description.key == "humidity":
            data = self._data.get_latest_humidities()
        elif self.entity_description.key == "rain":
            data = self._data.get_latest_rain()
        elif self.entity_description.key == "sum_rain_1":
            data = self._data.get_60_min_rain()
        elif self.entity_description.key == "sum_rain_24":
            data = self._data.get_24_h_rain()
        elif self.entity_description.key == "windstrength":
            data = self._data.get_latest_wind_strengths()
        elif self.entity_description.key == "guststrength":
            data = self._data.get_latest_gust_strengths()

        if data is None:
            if self.state is None:
                return
            _LOGGER.debug(
                "No station provides %s data in the area %s",
                self.entity_description.key,
                self._area_name,
            )
            self._attr_native_value = None
            return

        if values := [x for x in data.values() if x is not None]:
            if self._mode == "avg":
                self._attr_native_value = round(sum(values) / len(values), 1)
            elif self._mode == "max":
                self._attr_native_value = max(values)

        self._attr_available = self.state is not None
        self.async_write_ha_state()
