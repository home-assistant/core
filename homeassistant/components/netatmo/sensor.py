"""Support for the Netatmo Weather Service."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_entries_for_config_entry
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import CONF_WEATHER_AREAS, DATA_HANDLER, DOMAIN, MANUFACTURER, MODELS
from .helper import NetatmoArea
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)

SUPPORTED_PUBLIC_SENSOR_TYPES = [
    "temperature",
    "pressure",
    "humidity",
    "rain",
    "windstrength",
    "guststrength",
    "sum_rain_1",
    "sum_rain_24",
]

SENSOR_TYPES = {
    "temperature": [
        "Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "co2": ["CO2", CONCENTRATION_PARTS_PER_MILLION, "mdi:molecule-co2", None],
    "pressure": ["Pressure", "mbar", "mdi:gauge", None],
    "noise": ["Noise", "dB", "mdi:volume-high", None],
    "humidity": [
        "Humidity",
        UNIT_PERCENTAGE,
        "mdi:water-percent",
        DEVICE_CLASS_HUMIDITY,
    ],
    "rain": ["Rain", "mm", "mdi:weather-rainy", None],
    "sum_rain_1": ["sum_rain_1", "mm", "mdi:weather-rainy", None],
    "sum_rain_24": ["sum_rain_24", "mm", "mdi:weather-rainy", None],
    "battery_vp": ["Battery", "", "mdi:battery", None],
    "battery_lvl": ["Battery_lvl", "", "mdi:battery", None],
    "battery_percent": ["battery_percent", UNIT_PERCENTAGE, None, DEVICE_CLASS_BATTERY],
    "min_temp": ["Min Temp.", TEMP_CELSIUS, "mdi:thermometer", None],
    "max_temp": ["Max Temp.", TEMP_CELSIUS, "mdi:thermometer", None],
    "windangle": ["Angle", "", "mdi:compass", None],
    "windangle_value": ["Angle Value", "º", "mdi:compass", None],
    "windstrength": [
        "Wind Strength",
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        None,
    ],
    "gustangle": ["Gust Angle", "", "mdi:compass", None],
    "gustangle_value": ["Gust Angle Value", "º", "mdi:compass", None],
    "guststrength": [
        "Gust Strength",
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        None,
    ],
    "reachable": ["Reachability", "", "mdi:signal", None],
    "rf_status": ["Radio", "", "mdi:signal", None],
    "rf_status_lvl": ["Radio_lvl", "", "mdi:signal", None],
    "wifi_status": ["Wifi", "", "mdi:wifi", None],
    "wifi_status_lvl": ["Wifi_lvl", "dBm", "mdi:wifi", None],
    "health_idx": ["Health", "", "mdi:cloud", None],
}

MODULE_TYPE_OUTDOOR = "NAModule1"
MODULE_TYPE_WIND = "NAModule2"
MODULE_TYPE_RAIN = "NAModule3"
MODULE_TYPE_INDOOR = "NAModule4"

PUBLIC = "public"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo weather and homecoach platform."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    async def find_entities(data_class):
        """Find all entities."""
        await data_handler.register_data_class(data_class)

        all_module_infos = {}
        data = data_handler.data

        if not data.get(data_class):
            return []

        for station_id in data.get(data_class).stations:
            for module_id in data.get(data_class).get_modules(station_id):
                all_module_infos[module_id] = data.get(data_class).get_module(module_id)

            all_module_infos[station_id] = data.get(data_class).get_station(station_id)

        entities = []
        for module in all_module_infos.values():
            if "_id" not in module:
                _LOGGER.debug("Skipping module %s", module.get("module_name"))
                continue

            _LOGGER.debug(
                "Adding module %s %s", module.get("module_name"), module.get("_id"),
            )
            for condition in data[data_class].get_monitored_conditions(
                module_id=module["_id"]
            ):
                entities.append(
                    NetatmoSensor(data_handler, data_class, module, condition.lower())
                )

        await data_handler.unregister_data_class(data_class)
        return entities

    async def get_entities():
        """Retrieve Netatmo entities."""
        entities = []

        for data_class_name in ["WeatherStationData", "HomeCoachData"]:
            entities.extend(await find_entities(data_class_name))

        return entities

    async_add_entities(await get_entities(), True)

    @callback
    async def add_public_entities():
        """Retrieve Netatmo public weather entities."""
        data_class_name = "PublicData"
        entities = []
        for area in [
            NetatmoArea(**i) for i in entry.options.get(CONF_WEATHER_AREAS, {}).values()
        ]:
            await data_handler.register_data_class(
                data_class_name,
                LAT_NE=area.lat_ne,
                LON_NE=area.lon_ne,
                LAT_SW=area.lat_sw,
                LON_SW=area.lon_sw,
                area_name=area.area_name,
            )
            for sensor_type in SUPPORTED_PUBLIC_SENSOR_TYPES:
                entities.append(
                    NetatmoPublicSensor(data_handler, data_class, area, sensor_type,)
                )
            await data_handler.unregister_data_class(f"{data_class}-{area.area_name}")

        for device in async_entries_for_config_entry(device_registry, entry.entry_id):
            if device.model == "Public Weather stations":
                device_registry.async_remove_device(device.id)

        if entities:
            async_add_entities(entities)

    async_dispatcher_connect(
        hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}", add_public_entities
    )

    entry.add_update_listener(async_config_entry_updated)

    await add_public_entities()


async def async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle signals of config entry being updated."""
    async_dispatcher_send(hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}")


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Netatmo weather and homecoach platform."""
    return


class NetatmoSensor(NetatmoBase):
    """Implementation of a Netatmo sensor."""

    def __init__(self, data_handler, data_class_name, module_info, sensor_type):
        """Initialize the sensor."""
        super().__init__(data_handler)

        self._data_classes.append({"name": data_class})

        self._id = module_info["_id"]
        self._station_id = module_info.get("main_device", self._id)

        station = self._data.get_station(self._station_id)
        device = self._data.get_module(self._id)

        if not device:
            # Assume it's a station if module can't be found
            device = station

        if device["type"] in ("NHC", "NAMain"):
            self._device_name = module_info["station_name"]
        else:
            self._device_name = f"{station['station_name']} {module_info.get('module_name', device['type'])}"

        self._name = (
            f"{MANUFACTURER} {self._device_name} {SENSOR_TYPES[sensor_type][0]}"
        )
        self.type = sensor_type
        self._state = None
        self._device_class = SENSOR_TYPES[self.type][3]
        self._icon = SENSOR_TYPES[self.type][2]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._model = device["type"]
        self._unique_id = f"{self._id}-{self.type}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        if self._data is None:
            if self._state is None:
                return
            _LOGGER.warning("No data from update")
            self._state = None
            return

        data = self._data.get_last_data(station_id=self._station_id, exclude=3600).get(
            self._id
        )

        if data is None:
            if self._state:
                _LOGGER.debug("No data found for %s (%s)", self._device_name, self._id)
                _LOGGER.debug("data: %s", self._data)
            self._state = None
            return

        try:
            if self.type == "temperature":
                self._state = round(data["Temperature"], 1)
            elif self.type == "humidity":
                self._state = data["Humidity"]
            elif self.type == "rain":
                self._state = data["Rain"]
            elif self.type == "sum_rain_1":
                self._state = round(data["sum_rain_1"], 1)
            elif self.type == "sum_rain_24":
                self._state = data["sum_rain_24"]
            elif self.type == "noise":
                self._state = data["Noise"]
            elif self.type == "co2":
                self._state = data["CO2"]
            elif self.type == "pressure":
                self._state = round(data["Pressure"], 1)
            elif self.type == "battery_percent":
                self._state = data["battery_percent"]
            elif self.type == "battery_lvl":
                self._state = data["battery_vp"]
            elif self.type == "battery_vp" and self._model == MODULE_TYPE_WIND:
                if data["battery_vp"] >= 5590:
                    self._state = "Full"
                elif data["battery_vp"] >= 5180:
                    self._state = "High"
                elif data["battery_vp"] >= 4770:
                    self._state = "Medium"
                elif data["battery_vp"] >= 4360:
                    self._state = "Low"
                else:
                    self._state = "Very Low"
            elif self.type == "battery_vp" and self._model == MODULE_TYPE_RAIN:
                if data["battery_vp"] >= 5500:
                    self._state = "Full"
                elif data["battery_vp"] >= 5000:
                    self._state = "High"
                elif data["battery_vp"] >= 4500:
                    self._state = "Medium"
                elif data["battery_vp"] >= 4000:
                    self._state = "Low"
                else:
                    self._state = "Very Low"
            elif self.type == "battery_vp" and self._model == MODULE_TYPE_INDOOR:
                if data["battery_vp"] >= 5640:
                    self._state = "Full"
                elif data["battery_vp"] >= 5280:
                    self._state = "High"
                elif data["battery_vp"] >= 4920:
                    self._state = "Medium"
                elif data["battery_vp"] >= 4560:
                    self._state = "Low"
                else:
                    self._state = "Very Low"
            elif self.type == "battery_vp" and self._model == MODULE_TYPE_OUTDOOR:
                if data["battery_vp"] >= 5500:
                    self._state = "Full"
                elif data["battery_vp"] >= 5000:
                    self._state = "High"
                elif data["battery_vp"] >= 4500:
                    self._state = "Medium"
                elif data["battery_vp"] >= 4000:
                    self._state = "Low"
                else:
                    self._state = "Very Low"
            elif self.type == "min_temp":
                self._state = data["min_temp"]
            elif self.type == "max_temp":
                self._state = data["max_temp"]
            elif self.type == "windangle_value":
                self._state = data["WindAngle"]
            elif self.type == "windangle":
                if data["WindAngle"] >= 330:
                    self._state = "N (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 300:
                    self._state = "NW (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 240:
                    self._state = "W (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 210:
                    self._state = "SW (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 150:
                    self._state = "S (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 120:
                    self._state = "SE (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 60:
                    self._state = "E (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 30:
                    self._state = "NE (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 0:
                    self._state = "N (%d\xb0)" % data["WindAngle"]
            elif self.type == "windstrength":
                self._state = data["WindStrength"]
            elif self.type == "gustangle_value":
                self._state = data["GustAngle"]
            elif self.type == "gustangle":
                if data["GustAngle"] >= 330:
                    self._state = "N (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 300:
                    self._state = "NW (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 240:
                    self._state = "W (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 210:
                    self._state = "SW (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 150:
                    self._state = "S (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 120:
                    self._state = "SE (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 60:
                    self._state = "E (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 30:
                    self._state = "NE (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 0:
                    self._state = "N (%d\xb0)" % data["GustAngle"]
            elif self.type == "guststrength":
                self._state = data["GustStrength"]
            elif self.type == "reachable":
                self._state = data["reachable"]
            elif self.type == "rf_status_lvl":
                self._state = data["rf_status"]
            elif self.type == "rf_status":
                if data["rf_status"] >= 90:
                    self._state = "Low"
                elif data["rf_status"] >= 76:
                    self._state = "Medium"
                elif data["rf_status"] >= 60:
                    self._state = "High"
                elif data["rf_status"] <= 59:
                    self._state = "Full"
            elif self.type == "wifi_status_lvl":
                self._state = data["wifi_status"]
            elif self.type == "wifi_status":
                if data["wifi_status"] >= 86:
                    self._state = "Low"
                elif data["wifi_status"] >= 71:
                    self._state = "Medium"
                elif data["wifi_status"] >= 56:
                    self._state = "High"
                elif data["wifi_status"] <= 55:
                    self._state = "Full"
            elif self.type == "health_idx":
                if data["health_idx"] == 0:
                    self._state = "Healthy"
                elif data["health_idx"] == 1:
                    self._state = "Fine"
                elif data["health_idx"] == 2:
                    self._state = "Fair"
                elif data["health_idx"] == 3:
                    self._state = "Poor"
                elif data["health_idx"] == 4:
                    self._state = "Unhealthy"
        except KeyError:
            if self._state:
                _LOGGER.debug("No %s data found for %s", self.type, self._device_name)
            self._state = None
            return


class NetatmoPublicSensor(NetatmoBase):
    """Represent a single sensor in a Netatmo."""

    def __init__(self, data_handler, data_class, area, sensor_type):
        """Initialize the sensor."""
        super().__init__(data_handler)

        self._data_classes.append(
            {
                "name": data_class_name,
                "LAT_NE": area.lat_ne,
                "LON_NE": area.lon_ne,
                "LAT_SW": area.lat_sw,
                "LON_SW": area.lon_sw,
                "area_name": area.area_name,
            }
        )

        self.type = sensor_type
        self.area = area
        self._mode = area.mode
        self._area_name = area.area_name
        self._name = f"{MANUFACTURER} {self._area_name} {SENSOR_TYPES[self.type][0]}"
        self._state = None
        self._device_class = SENSOR_TYPES[self.type][3]
        self._icon = SENSOR_TYPES[self.type][2]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._show_on_map = area.show_on_map
        self._unique_id = f"{self._name.replace(' ', '-')}"
        self._model = PUBLIC

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._area_name)},
            "name": self._area_name,
            "manufacturer": MANUFACTURER,
            "model": MODELS[self._model],
        }

    @property
    def device_state_attributes(self):
        """Return the attributes of the device."""
        attrs = {}

        if self._show_on_map:
            attrs[ATTR_LATITUDE] = (self.area.lat_ne + self.area.lat_sw) / 2
            attrs[ATTR_LONGITUDE] = (self.area.lon_ne + self.area.lon_sw) / 2

        return attrs

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def _data(self):
        return self.data_handler.data[f"PublicData-{self._area_name}"]

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        if self._data is None:
            if self._state is None:
                return
            _LOGGER.warning("No data from update")
            self._state = None
            return

        data = None

        if self.type == "temperature":
            data = self._data.get_latest_temperatures()
        elif self.type == "pressure":
            data = self._data.get_latest_pressures()
        elif self.type == "humidity":
            data = self._data.get_latest_humidities()
        elif self.type == "rain":
            data = self._data.get_latest_rain()
        elif self.type == "sum_rain_1":
            data = self._data.get_60_min_rain()
        elif self.type == "sum_rain_24":
            data = self._data.get_24_h_rain()
        elif self.type == "windstrength":
            data = self._data.get_latest_wind_strengths()
        elif self.type == "guststrength":
            data = self._data.get_latest_gust_strengths()

        if not data:
            _LOGGER.debug(
                "No station provides %s data in the area %s", self.type, self._area_name
            )
            self._state = None
            return

        values = [x for x in data.values() if x is not None]
        if self._mode == "avg":
            self._state = round(sum(values) / len(values), 1)
        elif self._mode == "max":
            self._state = max(values)
