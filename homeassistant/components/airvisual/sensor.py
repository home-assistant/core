"""Support for AirVisual air quality sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_STATE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import AirVisualEntity
from .const import (
    CONF_CITY,
    CONF_COUNTRY,
    CONF_INTEGRATION_TYPE,
    DATA_COORDINATOR,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    INTEGRATION_TYPE_GEOGRAPHY_NAME,
)

ATTR_CITY = "city"
ATTR_COUNTRY = "country"
ATTR_POLLUTANT_SYMBOL = "pollutant_symbol"
ATTR_POLLUTANT_UNIT = "pollutant_unit"
ATTR_REGION = "region"

DEVICE_CLASS_POLLUTANT_LABEL = "airvisual__pollutant_label"
DEVICE_CLASS_POLLUTANT_LEVEL = "airvisual__pollutant_level"

SENSOR_KIND_AQI = "air_quality_index"
SENSOR_KIND_BATTERY_LEVEL = "battery_level"
SENSOR_KIND_CO2 = "carbon_dioxide"
SENSOR_KIND_HUMIDITY = "humidity"
SENSOR_KIND_LEVEL = "air_pollution_level"
SENSOR_KIND_PM_0_1 = "particulate_matter_0_1"
SENSOR_KIND_PM_1_0 = "particulate_matter_1_0"
SENSOR_KIND_PM_2_5 = "particulate_matter_2_5"
SENSOR_KIND_POLLUTANT = "main_pollutant"
SENSOR_KIND_SENSOR_LIFE = "sensor_life"
SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_VOC = "voc"

GEOGRAPHY_SENSORS = [
    (SENSOR_KIND_LEVEL, "Air Pollution Level", "mdi:gauge", None),
    (SENSOR_KIND_AQI, "Air Quality Index", "mdi:chart-line", "AQI"),
    (SENSOR_KIND_POLLUTANT, "Main Pollutant", "mdi:chemical-weapon", None),
]
GEOGRAPHY_SENSOR_LOCALES = {"cn": "Chinese", "us": "U.S."}

NODE_PRO_SENSORS = [
    (SENSOR_KIND_AQI, "Air Quality Index", None, "mdi:chart-line", "AQI"),
    (SENSOR_KIND_BATTERY_LEVEL, "Battery", DEVICE_CLASS_BATTERY, None, PERCENTAGE),
    (
        SENSOR_KIND_CO2,
        "C02",
        DEVICE_CLASS_CO2,
        None,
        CONCENTRATION_PARTS_PER_MILLION,
    ),
    (SENSOR_KIND_HUMIDITY, "Humidity", DEVICE_CLASS_HUMIDITY, None, PERCENTAGE),
    (
        SENSOR_KIND_PM_0_1,
        "PM 0.1",
        None,
        "mdi:sprinkler",
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    (
        SENSOR_KIND_PM_1_0,
        "PM 1.0",
        None,
        "mdi:sprinkler",
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    (
        SENSOR_KIND_PM_2_5,
        "PM 2.5",
        None,
        "mdi:sprinkler",
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    (
        SENSOR_KIND_TEMPERATURE,
        "Temperature",
        DEVICE_CLASS_TEMPERATURE,
        None,
        TEMP_CELSIUS,
    ),
    (
        SENSOR_KIND_VOC,
        "VOC",
        None,
        "mdi:sprinkler",
        CONCENTRATION_PARTS_PER_MILLION,
    ),
]

STATE_POLLUTANT_LABEL_CO = "co"
STATE_POLLUTANT_LABEL_N2 = "n2"
STATE_POLLUTANT_LABEL_O3 = "o3"
STATE_POLLUTANT_LABEL_P1 = "p1"
STATE_POLLUTANT_LABEL_P2 = "p2"
STATE_POLLUTANT_LABEL_S2 = "s2"

STATE_POLLUTANT_LEVEL_GOOD = "good"
STATE_POLLUTANT_LEVEL_MODERATE = "moderate"
STATE_POLLUTANT_LEVEL_UNHEALTHY_SENSITIVE = "unhealthy_sensitive"
STATE_POLLUTANT_LEVEL_UNHEALTHY = "unhealthy"
STATE_POLLUTANT_LEVEL_VERY_UNHEALTHY = "very_unhealthy"
STATE_POLLUTANT_LEVEL_HAZARDOUS = "hazardous"

POLLUTANT_LEVELS = {
    (0, 50): (STATE_POLLUTANT_LEVEL_GOOD, "mdi:emoticon-excited"),
    (51, 100): (STATE_POLLUTANT_LEVEL_MODERATE, "mdi:emoticon-happy"),
    (101, 150): (STATE_POLLUTANT_LEVEL_UNHEALTHY_SENSITIVE, "mdi:emoticon-neutral"),
    (151, 200): (STATE_POLLUTANT_LEVEL_UNHEALTHY, "mdi:emoticon-sad"),
    (201, 300): (STATE_POLLUTANT_LEVEL_VERY_UNHEALTHY, "mdi:emoticon-dead"),
    (301, 1000): (STATE_POLLUTANT_LEVEL_HAZARDOUS, "mdi:biohazard"),
}

POLLUTANT_UNITS = {
    "co": CONCENTRATION_PARTS_PER_MILLION,
    "n2": CONCENTRATION_PARTS_PER_BILLION,
    "o3": CONCENTRATION_PARTS_PER_BILLION,
    "p1": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "p2": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "s2": CONCENTRATION_PARTS_PER_BILLION,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirVisual sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id]

    sensors: list[AirVisualGeographySensor | AirVisualNodeProSensor]
    if config_entry.data[CONF_INTEGRATION_TYPE] in [
        INTEGRATION_TYPE_GEOGRAPHY_COORDS,
        INTEGRATION_TYPE_GEOGRAPHY_NAME,
    ]:
        sensors = [
            AirVisualGeographySensor(
                coordinator,
                config_entry,
                kind,
                name,
                icon,
                unit,
                locale,
            )
            for locale in GEOGRAPHY_SENSOR_LOCALES
            for kind, name, icon, unit in GEOGRAPHY_SENSORS
        ]
    else:
        sensors = [
            AirVisualNodeProSensor(coordinator, kind, name, device_class, icon, unit)
            for kind, name, device_class, icon, unit in NODE_PRO_SENSORS
        ]

    async_add_entities(sensors, True)


class AirVisualGeographySensor(AirVisualEntity, SensorEntity):
    """Define an AirVisual sensor related to geography data via the Cloud API."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        kind: str,
        name: str,
        icon: str,
        unit: str | None,
        locale: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        if kind == SENSOR_KIND_LEVEL:
            self._attr_device_class = DEVICE_CLASS_POLLUTANT_LEVEL
        elif kind == SENSOR_KIND_POLLUTANT:
            self._attr_device_class = DEVICE_CLASS_POLLUTANT_LABEL
        self._attr_extra_state_attributes.update(
            {
                ATTR_CITY: config_entry.data.get(CONF_CITY),
                ATTR_STATE: config_entry.data.get(CONF_STATE),
                ATTR_COUNTRY: config_entry.data.get(CONF_COUNTRY),
            }
        )
        self._attr_icon = icon
        self._attr_name = f"{GEOGRAPHY_SENSOR_LOCALES[locale]} {name}"
        self._attr_unique_id = f"{config_entry.unique_id}_{locale}_{kind}"
        self._attr_unit_of_measurement = unit
        self._config_entry = config_entry
        self._kind = kind
        self._locale = locale

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data["current"]["pollution"]

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        try:
            data = self.coordinator.data["current"]["pollution"]
        except KeyError:
            return

        if self._kind == SENSOR_KIND_LEVEL:
            aqi = data[f"aqi{self._locale}"]
            [(self._attr_state, self._attr_icon)] = [
                (name, icon)
                for (floor, ceiling), (name, icon) in POLLUTANT_LEVELS.items()
                if floor <= aqi <= ceiling
            ]
        elif self._kind == SENSOR_KIND_AQI:
            self._attr_state = data[f"aqi{self._locale}"]
        elif self._kind == SENSOR_KIND_POLLUTANT:
            symbol = data[f"main{self._locale}"]
            self._attr_state = symbol
            self._attr_extra_state_attributes.update(
                {
                    ATTR_POLLUTANT_SYMBOL: symbol,
                    ATTR_POLLUTANT_UNIT: POLLUTANT_UNITS[symbol],
                }
            )

        # Displaying the geography on the map relies upon putting the latitude/longitude
        # in the entity attributes with "latitude" and "longitude" as the keys.
        # Conversely, we can hide the location on the map by using other keys, like
        # "lati" and "long".
        #
        # We use any coordinates in the config entry and, in the case of a geography by
        # name, we fall back to the latitude longitude provided in the coordinator data:
        latitude = self._config_entry.data.get(
            CONF_LATITUDE,
            self.coordinator.data["location"]["coordinates"][1],
        )
        longitude = self._config_entry.data.get(
            CONF_LONGITUDE,
            self.coordinator.data["location"]["coordinates"][0],
        )

        if self._config_entry.options[CONF_SHOW_ON_MAP]:
            self._attr_extra_state_attributes[ATTR_LATITUDE] = latitude
            self._attr_extra_state_attributes[ATTR_LONGITUDE] = longitude
            self._attr_extra_state_attributes.pop("lati", None)
            self._attr_extra_state_attributes.pop("long", None)
        else:
            self._attr_extra_state_attributes["lati"] = latitude
            self._attr_extra_state_attributes["long"] = longitude
            self._attr_extra_state_attributes.pop(ATTR_LATITUDE, None)
            self._attr_extra_state_attributes.pop(ATTR_LONGITUDE, None)


class AirVisualNodeProSensor(AirVisualEntity, SensorEntity):
    """Define an AirVisual sensor related to a Node/Pro unit."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        kind: str,
        name: str,
        device_class: str | None,
        icon: str | None,
        unit: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_name = (
            f"{coordinator.data['settings']['node_name']} Node/Pro: {name}"
        )
        self._attr_unique_id = f"{coordinator.data['serial_number']}_{kind}"
        self._attr_unit_of_measurement = unit
        self._kind = kind

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.data["serial_number"])},
            "name": self.coordinator.data["settings"]["node_name"],
            "manufacturer": "AirVisual",
            "model": f'{self.coordinator.data["status"]["model"]}',
            "sw_version": (
                f'Version {self.coordinator.data["status"]["system_version"]}'
                f'{self.coordinator.data["status"]["app_version"]}'
            ),
        }

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        if self._kind == SENSOR_KIND_AQI:
            if self.coordinator.data["settings"]["is_aqi_usa"]:
                self._attr_state = self.coordinator.data["measurements"]["aqi_us"]
            else:
                self._attr_state = self.coordinator.data["measurements"]["aqi_cn"]
        elif self._kind == SENSOR_KIND_BATTERY_LEVEL:
            self._attr_state = self.coordinator.data["status"]["battery"]
        elif self._kind == SENSOR_KIND_CO2:
            self._attr_state = self.coordinator.data["measurements"].get("co2")
        elif self._kind == SENSOR_KIND_HUMIDITY:
            self._attr_state = self.coordinator.data["measurements"].get("humidity")
        elif self._kind == SENSOR_KIND_PM_0_1:
            self._attr_state = self.coordinator.data["measurements"].get("pm0_1")
        elif self._kind == SENSOR_KIND_PM_1_0:
            self._attr_state = self.coordinator.data["measurements"].get("pm1_0")
        elif self._kind == SENSOR_KIND_PM_2_5:
            self._attr_state = self.coordinator.data["measurements"].get("pm2_5")
        elif self._kind == SENSOR_KIND_TEMPERATURE:
            self._attr_state = self.coordinator.data["measurements"].get(
                "temperature_C"
            )
        elif self._kind == SENSOR_KIND_VOC:
            self._attr_state = self.coordinator.data["measurements"].get("voc")
