"""Support for Meteo-France raining forecast sensor."""
import logging

from meteofrance_api.helpers import (
    get_warning_text_status_from_indice_color,
    readeable_phenomenoms_dict,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_NEXT_RAIN_1_HOUR_FORECAST,
    ATTR_NEXT_RAIN_DT_REF,
    ATTRIBUTION,
    COORDINATOR_ALERT,
    COORDINATOR_FORECAST,
    COORDINATOR_RAIN,
    DOMAIN,
    ENTITY_API_DATA_PATH,
    ENTITY_DEVICE_CLASS,
    ENTITY_ENABLE,
    ENTITY_ICON,
    ENTITY_NAME,
    ENTITY_UNIT,
    MANUFACTURER,
    MODEL,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteo-France sensor platform."""
    coordinator_forecast = hass.data[DOMAIN][entry.entry_id][COORDINATOR_FORECAST]
    coordinator_rain = hass.data[DOMAIN][entry.entry_id][COORDINATOR_RAIN]
    coordinator_alert = hass.data[DOMAIN][entry.entry_id][COORDINATOR_ALERT]

    entities = []
    for sensor_type in SENSOR_TYPES:
        if sensor_type == "next_rain":
            if coordinator_rain:
                entities.append(MeteoFranceRainSensor(sensor_type, coordinator_rain))

        elif sensor_type == "weather_alert":
            if coordinator_alert:
                entities.append(MeteoFranceAlertSensor(sensor_type, coordinator_alert))

        elif sensor_type in ["rain_chance", "freeze_chance", "snow_chance"]:
            if coordinator_forecast.data.probability_forecast:
                entities.append(MeteoFranceSensor(sensor_type, coordinator_forecast))
            else:
                _LOGGER.warning(
                    "Sensor %s skipped for %s as data is missing in the API",
                    sensor_type,
                    coordinator_forecast.data.position["name"],
                )

        else:
            entities.append(MeteoFranceSensor(sensor_type, coordinator_forecast))

    async_add_entities(
        entities,
        False,
    )


class MeteoFranceSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Meteo-France sensor."""

    def __init__(self, sensor_type: str, coordinator: DataUpdateCoordinator):
        """Initialize the Meteo-France sensor."""
        super().__init__(coordinator)
        self._type = sensor_type
        if hasattr(self.coordinator.data, "position"):
            city_name = self.coordinator.data.position["name"]
            self._name = f"{city_name} {SENSOR_TYPES[self._type][ENTITY_NAME]}"
            self._unique_id = f"{self.coordinator.data.position['lat']},{self.coordinator.data.position['lon']}_{self._type}"

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.platform.config_entry.unique_id)},
            "name": self.coordinator.name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "entry_type": "service",
        }

    @property
    def state(self):
        """Return the state."""
        path = SENSOR_TYPES[self._type][ENTITY_API_DATA_PATH].split(":")
        data = getattr(self.coordinator.data, path[0])

        # Specific case for probability forecast
        if path[0] == "probability_forecast":
            if len(path) == 3:
                # This is a fix compared to other entitty as first index is always null in API result for unknown reason
                value = _find_first_probability_forecast_not_null(data, path)
            else:
                value = data[0][path[1]]

        # General case
        else:
            if len(path) == 3:
                value = data[path[1]][path[2]]
            else:
                value = data[path[1]]

        if self._type in ["wind_speed", "wind_gust"]:
            # convert API wind speed from m/s to km/h
            value = round(value * 3.6)
        return value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._type][ENTITY_UNIT]

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_TYPES[self._type][ENTITY_ICON]

    @property
    def device_class(self):
        """Return the device class."""
        return SENSOR_TYPES[self._type][ENTITY_DEVICE_CLASS]

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return SENSOR_TYPES[self._type][ENTITY_ENABLE]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}


class MeteoFranceRainSensor(MeteoFranceSensor):
    """Representation of a Meteo-France rain sensor."""

    @property
    def state(self):
        """Return the state."""
        # search first cadran with rain
        next_rain = next(
            (cadran for cadran in self.coordinator.data.forecast if cadran["rain"] > 1),
            None,
        )
        return (
            dt_util.utc_from_timestamp(next_rain["dt"]).isoformat()
            if next_rain
            else None
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        reference_dt = self.coordinator.data.forecast[0]["dt"]
        return {
            ATTR_NEXT_RAIN_DT_REF: dt_util.utc_from_timestamp(reference_dt).isoformat(),
            ATTR_NEXT_RAIN_1_HOUR_FORECAST: {
                f"{int((item['dt'] - reference_dt) / 60)} min": item["desc"]
                for item in self.coordinator.data.forecast
            },
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class MeteoFranceAlertSensor(MeteoFranceSensor):
    """Representation of a Meteo-France alert sensor."""

    def __init__(self, sensor_type: str, coordinator: DataUpdateCoordinator):
        """Initialize the Meteo-France sensor."""
        super().__init__(sensor_type, coordinator)
        dept_code = self.coordinator.data.domain_id
        self._name = f"{dept_code} {SENSOR_TYPES[self._type][ENTITY_NAME]}"
        self._unique_id = self._name

    @property
    def state(self):
        """Return the state."""
        return get_warning_text_status_from_indice_color(
            self.coordinator.data.get_domain_max_color()
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            **readeable_phenomenoms_dict(self.coordinator.data.phenomenons_max_colors),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


def _find_first_probability_forecast_not_null(
    probability_forecast: list, path: list
) -> int:
    """Search the first not None value in the first forecast elements."""
    for forecast in probability_forecast[0:3]:
        if forecast[path[1]][path[2]] is not None:
            return forecast[path[1]][path[2]]

    # Default return value if no value founded
    return None
