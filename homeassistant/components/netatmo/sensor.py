"""Support for the Netatmo Weather Service."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_MBAR,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_entries_for_config_entry
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import CONF_WEATHER_AREAS, DATA_HANDLER, DOMAIN, MANUFACTURER, SIGNAL_NAME
from .data_handler import (
    HOMECOACH_DATA_CLASS_NAME,
    PUBLICDATA_DATA_CLASS_NAME,
    WEATHERSTATION_DATA_CLASS_NAME,
)
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
    "temperature": ["Temperature", TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    "co2": ["CO2", CONCENTRATION_PARTS_PER_MILLION, "mdi:molecule-co2", None],
    "pressure": ["Pressure", PRESSURE_MBAR, None, DEVICE_CLASS_PRESSURE],
    "noise": ["Noise", "dB", "mdi:volume-high", None],
    "humidity": ["Humidity", PERCENTAGE, None, DEVICE_CLASS_HUMIDITY],
    "rain": ["Rain", LENGTH_MILLIMETERS, "mdi:weather-rainy", None],
    "sum_rain_1": ["Rain last hour", LENGTH_MILLIMETERS, "mdi:weather-rainy", None],
    "sum_rain_24": ["Rain last 24h", LENGTH_MILLIMETERS, "mdi:weather-rainy", None],
    "battery_vp": ["Battery", "", "mdi:battery", None],
    "battery_lvl": ["Battery Level", "", "mdi:battery", None],
    "battery_percent": ["Battery Percent", PERCENTAGE, None, DEVICE_CLASS_BATTERY],
    "min_temp": ["Min Temp.", TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    "max_temp": ["Max Temp.", TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    "windangle": ["Direction", None, "mdi:compass-outline", None],
    "windangle_value": ["Angle", DEGREE, "mdi:compass-outline", None],
    "windstrength": [
        "Wind Strength",
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        None,
    ],
    "gustangle": ["Gust Direction", None, "mdi:compass-outline", None],
    "gustangle_value": ["Gust Angle", DEGREE, "mdi:compass-outline", None],
    "guststrength": [
        "Gust Strength",
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        None,
    ],
    "reachable": ["Reachability", None, "mdi:signal", None],
    "rf_status": ["Radio", None, "mdi:signal", None],
    "rf_status_lvl": ["Radio Level", "", None, DEVICE_CLASS_SIGNAL_STRENGTH],
    "wifi_status": ["Wifi", None, "mdi:wifi", None],
    "wifi_status_lvl": ["Wifi Level", "dBm", None, DEVICE_CLASS_SIGNAL_STRENGTH],
    "health_idx": ["Health", None, "mdi:cloud", None],
}

MODULE_TYPE_OUTDOOR = "NAModule1"
MODULE_TYPE_WIND = "NAModule2"
MODULE_TYPE_RAIN = "NAModule3"
MODULE_TYPE_INDOOR = "NAModule4"

BATTERY_VALUES = {
    MODULE_TYPE_WIND: {"Full": 5590, "High": 5180, "Medium": 4770, "Low": 4360},
    MODULE_TYPE_RAIN: {"Full": 5500, "High": 5000, "Medium": 4500, "Low": 4000},
    MODULE_TYPE_INDOOR: {"Full": 5500, "High": 5280, "Medium": 4920, "Low": 4560},
    MODULE_TYPE_OUTDOOR: {"Full": 5500, "High": 5000, "Medium": 4500, "Low": 4000},
}

PUBLIC = "public"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo weather and homecoach platform."""
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    async def find_entities(data_class_name):
        """Find all entities."""
        await data_handler.register_data_class(data_class_name, data_class_name, None)

        all_module_infos = {}
        data = data_handler.data

        if not data.get(data_class_name):
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

            _LOGGER.debug(
                "Adding module %s %s",
                module.get("module_name"),
                module.get("_id"),
            )
            conditions = [
                c.lower()
                for c in data_class.get_monitored_conditions(module_id=module["_id"])
            ]
            for condition in conditions:
                if f"{condition}_value" in SENSOR_TYPES:
                    conditions.append(f"{condition}_value")
                elif f"{condition}_lvl" in SENSOR_TYPES:
                    conditions.append(f"{condition}_lvl")
                elif condition == "battery_vp":
                    conditions.append("battery_lvl")

            for condition in conditions:
                entities.append(
                    NetatmoSensor(data_handler, data_class_name, module, condition)
                )

        return entities

    for data_class_name in [
        WEATHERSTATION_DATA_CLASS_NAME,
        HOMECOACH_DATA_CLASS_NAME,
    ]:
        async_add_entities(await find_entities(data_class_name), True)

    device_registry = await hass.helpers.device_registry.async_get_registry()

    @callback
    async def add_public_entities(update=True):
        """Retrieve Netatmo public weather entities."""
        entities = {
            device.name: device.id
            for device in async_entries_for_config_entry(
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

            await data_handler.register_data_class(
                PUBLICDATA_DATA_CLASS_NAME,
                signal_name,
                None,
                LAT_NE=area.lat_ne,
                LON_NE=area.lon_ne,
                LAT_SW=area.lat_sw,
                LON_SW=area.lon_sw,
            )
            for sensor_type in SUPPORTED_PUBLIC_SENSOR_TYPES:
                new_entities.append(
                    NetatmoPublicSensor(data_handler, area, sensor_type)
                )

        for device_id in entities.values():
            device_registry.async_remove_device(device_id)

        if new_entities:
            async_add_entities(new_entities)

    async_dispatcher_connect(
        hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}", add_public_entities
    )

    entry.add_update_listener(async_config_entry_updated)

    await add_public_entities(False)


async def async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle signals of config entry being updated."""
    async_dispatcher_send(hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}")


class NetatmoSensor(NetatmoBase):
    """Implementation of a Netatmo sensor."""

    def __init__(self, data_handler, data_class_name, module_info, sensor_type):
        """Initialize the sensor."""
        super().__init__(data_handler)

        self._data_classes.append(
            {"name": data_class_name, SIGNAL_NAME: data_class_name}
        )

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
        """Return entity availability."""
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
                _LOGGER.debug(
                    "No data found for %s - %s (%s)",
                    self.name,
                    self._device_name,
                    self._id,
                )
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
            elif self.type == "battery_vp":
                self._state = process_battery(data["battery_vp"], self._model)
            elif self.type == "min_temp":
                self._state = data["min_temp"]
            elif self.type == "max_temp":
                self._state = data["max_temp"]
            elif self.type == "windangle_value":
                self._state = data["WindAngle"]
            elif self.type == "windangle":
                self._state = process_angle(data["WindAngle"])
            elif self.type == "windstrength":
                self._state = data["WindStrength"]
            elif self.type == "gustangle_value":
                self._state = data["GustAngle"]
            elif self.type == "gustangle":
                self._state = process_angle(data["GustAngle"])
            elif self.type == "guststrength":
                self._state = data["GustStrength"]
            elif self.type == "reachable":
                self._state = data["reachable"]
            elif self.type == "rf_status_lvl":
                self._state = data["rf_status"]
            elif self.type == "rf_status":
                self._state = process_rf(data["rf_status"])
            elif self.type == "wifi_status_lvl":
                self._state = data["wifi_status"]
            elif self.type == "wifi_status":
                self._state = process_wifi(data["wifi_status"])
            elif self.type == "health_idx":
                self._state = process_health(data["health_idx"])
        except KeyError:
            if self._state:
                _LOGGER.debug("No %s data found for %s", self.type, self._device_name)
            self._state = None
            return


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
    values = BATTERY_VALUES[model]

    if data >= values["Full"]:
        return "Full"
    if data >= values["High"]:
        return "High"
    if data >= values["Medium"]:
        return "Medium"
    if data >= values["Low"]:
        return "Low"
    return "Very Low"


def process_health(health):
    """Process health index and return string for display."""
    if health == 0:
        return "Healthy"
    if health == 1:
        return "Fine"
    if health == 2:
        return "Fair"
    if health == 3:
        return "Poor"
    if health == 4:
        return "Unhealthy"


def process_rf(strength):
    """Process wifi signal strength and return string for display."""
    if strength >= 90:
        return "Low"
    if strength >= 76:
        return "Medium"
    if strength >= 60:
        return "High"
    return "Full"


def process_wifi(strength):
    """Process wifi signal strength and return string for display."""
    if strength >= 86:
        return "Low"
    if strength >= 71:
        return "Medium"
    if strength >= 56:
        return "High"
    return "Full"


class NetatmoPublicSensor(NetatmoBase):
    """Represent a single sensor in a Netatmo."""

    def __init__(self, data_handler, area, sensor_type):
        """Initialize the sensor."""
        super().__init__(data_handler)

        self._signal_name = f"{PUBLICDATA_DATA_CLASS_NAME}-{area.uuid}"

        self._data_classes.append(
            {
                "name": PUBLICDATA_DATA_CLASS_NAME,
                "LAT_NE": area.lat_ne,
                "LON_NE": area.lon_ne,
                "LAT_SW": area.lat_sw,
                "LON_SW": area.lon_sw,
                "area_name": area.area_name,
                SIGNAL_NAME: self._signal_name,
            }
        )

        self.type = sensor_type
        self.area = area
        self._mode = area.mode
        self._area_name = area.area_name
        self._id = self._area_name
        self._device_name = f"{self._area_name}"
        self._name = f"{MANUFACTURER} {self._device_name} {SENSOR_TYPES[self.type][0]}"
        self._state = None
        self._device_class = SENSOR_TYPES[self.type][3]
        self._icon = SENSOR_TYPES[self.type][2]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._show_on_map = area.show_on_map
        self._unique_id = f"{self._device_name.replace(' ', '-')}-{self.type}"
        self._model = PUBLIC

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

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
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def _data(self):
        return self.data_handler.data[self._signal_name]

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        self.data_handler.listeners.append(
            async_dispatcher_connect(
                self.hass,
                f"netatmo-config-{self.device_info['name']}",
                self.async_config_update_callback,
            )
        )

    async def async_config_update_callback(self, area):
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
                "LAT_NE": area.lat_ne,
                "LON_NE": area.lon_ne,
                "LAT_SW": area.lat_sw,
                "LON_SW": area.lon_sw,
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
            LAT_NE=area.lat_ne,
            LON_NE=area.lon_ne,
            LAT_SW=area.lat_sw,
            LON_SW=area.lon_sw,
        )

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
            if self._state is None:
                return
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
