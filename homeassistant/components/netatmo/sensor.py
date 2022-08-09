"""Support for the Netatmo Weather Service."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import NamedTuple, cast

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
    PRESSURE_MBAR,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    SOUND_PRESSURE_DB,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_WEATHER_AREAS,
    DATA_HANDLER,
    DOMAIN,
    NETATMO_CREATE_BATTERY,
    SIGNAL_NAME,
    TYPE_WEATHER,
)
from .data_handler import (
    HOMECOACH_DATA_CLASS_NAME,
    PUBLICDATA_DATA_CLASS_NAME,
    WEATHERSTATION_DATA_CLASS_NAME,
    NetatmoDataHandler,
    NetatmoDevice,
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


SENSOR_TYPES: tuple[NetatmoSensorEntityDescription, ...] = (
    NetatmoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        netatmo_name="Temperature",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=TEMP_CELSIUS,
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
        netatmo_name="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO2,
    ),
    NetatmoSensorEntityDescription(
        key="pressure",
        name="Pressure",
        netatmo_name="Pressure",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=PRESSURE_MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRESSURE,
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
        netatmo_name="Noise",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=SOUND_PRESSURE_DB,
        icon="mdi:volume-high",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="humidity",
        name="Humidity",
        netatmo_name="Humidity",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    NetatmoSensorEntityDescription(
        key="rain",
        name="Rain",
        netatmo_name="Rain",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-rainy",
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_1",
        name="Rain last hour",
        netatmo_name="sum_rain_1",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:weather-rainy",
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_24",
        name="Rain today",
        netatmo_name="sum_rain_24",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:weather-rainy",
    ),
    NetatmoSensorEntityDescription(
        key="battery_percent",
        name="Battery Percent",
        netatmo_name="battery_percent",
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
    NetatmoSensorEntityDescription(
        key="windangle",
        name="Direction",
        netatmo_name="WindAngle",
        entity_registry_enabled_default=True,
        icon="mdi:compass-outline",
    ),
    NetatmoSensorEntityDescription(
        key="windangle_value",
        name="Angle",
        netatmo_name="WindAngle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="windstrength",
        name="Wind Strength",
        netatmo_name="WindStrength",
        entity_registry_enabled_default=True,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="gustangle",
        name="Gust Direction",
        netatmo_name="GustAngle",
        entity_registry_enabled_default=False,
        icon="mdi:compass-outline",
    ),
    NetatmoSensorEntityDescription(
        key="gustangle_value",
        name="Gust Angle",
        netatmo_name="GustAngle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="guststrength",
        name="Gust Strength",
        netatmo_name="GustStrength",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        icon="mdi:weather-windy",
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
        netatmo_name="rf_status",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:signal",
    ),
    NetatmoSensorEntityDescription(
        key="rf_status_lvl",
        name="Radio Level",
        netatmo_name="rf_status",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    ),
    NetatmoSensorEntityDescription(
        key="wifi_status",
        name="Wifi",
        netatmo_name="wifi_status",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:wifi",
    ),
    NetatmoSensorEntityDescription(
        key="wifi_status_lvl",
        name="Wifi Level",
        netatmo_name="wifi_status",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    ),
    NetatmoSensorEntityDescription(
        key="health_idx",
        name="Health",
        netatmo_name="health_idx",
        entity_registry_enabled_default=True,
        icon="mdi:cloud",
    ),
)
SENSOR_TYPES_KEYS = [desc.key for desc in SENSOR_TYPES]

MODULE_TYPE_OUTDOOR = "NAModule1"
MODULE_TYPE_WIND = "NAModule2"
MODULE_TYPE_RAIN = "NAModule3"
MODULE_TYPE_INDOOR = "NAModule4"


class BatteryData(NamedTuple):
    """Metadata for a batter."""

    full: int
    high: int
    medium: int
    low: int


BATTERY_VALUES = {
    MODULE_TYPE_WIND: BatteryData(
        full=5590,
        high=5180,
        medium=4770,
        low=4360,
    ),
    MODULE_TYPE_RAIN: BatteryData(
        full=5500,
        high=5000,
        medium=4500,
        low=4000,
    ),
    MODULE_TYPE_INDOOR: BatteryData(
        full=5500,
        high=5280,
        medium=4920,
        low=4560,
    ),
    MODULE_TYPE_OUTDOOR: BatteryData(
        full=5500,
        high=5000,
        medium=4500,
        low=4000,
    ),
}

PUBLIC = "public"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo weather and homecoach platform."""
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]
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
                    for description in SENSOR_TYPES
                    if description.key in conditions
                ]
            )

        _LOGGER.debug("Adding weather sensors %s", entities)
        return entities

    for data_class_name in (
        WEATHERSTATION_DATA_CLASS_NAME,
        HOMECOACH_DATA_CLASS_NAME,
    ):
        data_class = data_handler.data.get(data_class_name)

        if data_class and data_class.raw_data:
            platform_not_ready = False

        async_add_entities(await find_entities(data_class_name), True)

    device_registry = dr.async_get(hass)

    async def add_public_entities(update: bool = True) -> None:
        """Retrieve Netatmo public weather entities."""
        entities = {
            device.name: device.id
            for device in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            )
            if device.model == "Public Weather stations"
        }

        new_entities = []
        for area in [
            NetatmoArea(**i) for i in entry.options.get(CONF_WEATHER_AREAS, {}).values()
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

            await data_handler.subscribe(
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

    @callback
    def _create_entity(netatmo_device: NetatmoDevice) -> None:
        entity = NetatmoClimateBatterySensor(netatmo_device)
        _LOGGER.debug("Adding climate battery sensor %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_BATTERY, _create_entity)
    )

    await add_public_entities(False)

    if platform_not_ready:
        raise PlatformNotReady


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

        self._publishers.append({"name": data_class_name, SIGNAL_NAME: data_class_name})

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

        self._attr_name = f"{self._device_name} {description.name}"
        self._model = device["type"]
        self._netatmo_type = TYPE_WEATHER
        self._attr_unique_id = f"{self._id}-{description.key}"

    @property
    def _data(self) -> pyatmo.AsyncWeatherStationData:
        """Return data for this entity."""
        return cast(
            pyatmo.AsyncWeatherStationData,
            self.data_handler.data[self._publishers[0]["name"]],
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
            key="battery_percent",
            name="Battery Percent",
            netatmo_name="battery_percent",
            entity_registry_enabled_default=True,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.BATTERY,
        )

        self._module = netatmo_device.device
        self._id = netatmo_device.parent_id
        self._attr_name = f"{self._module.name} {self.entity_description.name}"

        self._signal_name = netatmo_device.signal_name
        self._room_id = self._module.room_id
        self._model = getattr(self._module.device_type, "value")

        self._attr_unique_id = (
            f"{self._id}-{self._module.entity_id}-{self.entity_description.key}"
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
                self._attr_native_value = None
            return

        self._attr_available = True
        self._attr_native_value = self._process_battery_state()

    def _process_battery_state(self) -> int | None:
        """Construct room status."""
        if battery_state := self._module.battery_state:
            return process_battery_percentage(battery_state)

        return None


def process_battery_percentage(data: str) -> int:
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


def process_battery(data: int, model: str) -> str:
    """Process battery data and return string for display."""
    battery_data = BATTERY_VALUES[model]

    if data >= battery_data.full:
        return "Full"
    if data >= battery_data.high:
        return "High"
    if data >= battery_data.medium:
        return "Medium"
    if data >= battery_data.low:
        return "Low"
    return "Very Low"


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

        self._publishers.append(
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

        await self.data_handler.unsubscribe(
            self._signal_name, self.async_update_callback
        )

        self.area = area
        self._signal_name = f"{PUBLICDATA_DATA_CLASS_NAME}-{area.uuid}"
        self._publishers = [
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
        await self.data_handler.subscribe(
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
