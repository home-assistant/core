"""Support for AirVisual air quality sensors."""
from __future__ import annotations

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
    ATTR_STATE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import AirVisualEntity
from .const import CONF_CITY, CONF_COUNTRY, DOMAIN

ATTR_CITY = "city"
ATTR_COUNTRY = "country"
ATTR_POLLUTANT_SYMBOL = "pollutant_symbol"
ATTR_POLLUTANT_UNIT = "pollutant_unit"
ATTR_REGION = "region"

SENSOR_KIND_AQI = "air_quality_index"
SENSOR_KIND_LEVEL = "air_pollution_level"
SENSOR_KIND_POLLUTANT = "main_pollutant"

GEOGRAPHY_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_KIND_LEVEL,
        name="Air pollution level",
        icon="mdi:gauge",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "good",
            "moderate",
            "unhealthy",
            "unhealthy_sensitive",
            "very_unhealthy",
            "hazardous",
        ],
        translation_key="pollutant_level",
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_AQI,
        name="Air quality index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_POLLUTANT,
        name="Main pollutant",
        icon="mdi:chemical-weapon",
        device_class=SensorDeviceClass.ENUM,
        options=["co", "n2", "o3", "p1", "p2", "s2"],
        translation_key="pollutant_label",
    ),
)
GEOGRAPHY_SENSOR_LOCALES = {"cn": "Chinese", "us": "U.S."}


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
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AirVisual sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AirVisualGeographySensor(coordinator, entry, description, locale)
        for locale in GEOGRAPHY_SENSOR_LOCALES
        for description in GEOGRAPHY_SENSOR_DESCRIPTIONS
    )


class AirVisualGeographySensor(AirVisualEntity, SensorEntity):
    """Define an AirVisual sensor related to geography data via the Cloud API."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
        locale: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, description)

        self._attr_extra_state_attributes.update(
            {
                ATTR_CITY: entry.data.get(CONF_CITY),
                ATTR_STATE: entry.data.get(CONF_STATE),
                ATTR_COUNTRY: entry.data.get(CONF_COUNTRY),
            }
        )
        self._attr_name = f"{GEOGRAPHY_SENSOR_LOCALES[locale]} {description.name}"
        self._attr_unique_id = f"{entry.unique_id}_{locale}_{description.key}"
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

        if self.entity_description.key == SENSOR_KIND_LEVEL:
            aqi = data[f"aqi{self._locale}"]
            [(self._attr_native_value, self._attr_icon)] = [
                (name, icon)
                for (floor, ceiling), (name, icon) in POLLUTANT_LEVELS.items()
                if floor <= aqi <= ceiling
            ]
        elif self.entity_description.key == SENSOR_KIND_AQI:
            self._attr_native_value = data[f"aqi{self._locale}"]
        elif self.entity_description.key == SENSOR_KIND_POLLUTANT:
            symbol = data[f"main{self._locale}"]
            self._attr_native_value = symbol
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
        latitude = self._entry.data.get(
            CONF_LATITUDE,
            self.coordinator.data["location"]["coordinates"][1],
        )
        longitude = self._entry.data.get(
            CONF_LONGITUDE,
            self.coordinator.data["location"]["coordinates"][0],
        )

        if self._entry.options[CONF_SHOW_ON_MAP]:
            self._attr_extra_state_attributes[ATTR_LATITUDE] = latitude
            self._attr_extra_state_attributes[ATTR_LONGITUDE] = longitude
            self._attr_extra_state_attributes.pop("lati", None)
            self._attr_extra_state_attributes.pop("long", None)
        else:
            self._attr_extra_state_attributes["lati"] = latitude
            self._attr_extra_state_attributes["long"] = longitude
            self._attr_extra_state_attributes.pop(ATTR_LATITUDE, None)
            self._attr_extra_state_attributes.pop(ATTR_LONGITUDE, None)
