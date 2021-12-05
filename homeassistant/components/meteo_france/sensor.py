"""Support for Meteo-France raining forecast sensor."""
from meteofrance_api.helpers import (
    get_warning_text_status_from_indice_color,
    readeable_phenomenoms_dict,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
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
    MANUFACTURER,
    MODEL,
    SENSOR_TYPES,
    SENSOR_TYPES_ALERT,
    SENSOR_TYPES_PROBABILITY,
    SENSOR_TYPES_RAIN,
    MeteoFranceSensorEntityDescription,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteo-France sensor platform."""
    coordinator_forecast = hass.data[DOMAIN][entry.entry_id][COORDINATOR_FORECAST]
    coordinator_rain = hass.data[DOMAIN][entry.entry_id][COORDINATOR_RAIN]
    coordinator_alert = hass.data[DOMAIN][entry.entry_id][COORDINATOR_ALERT]

    entities = [
        MeteoFranceSensor(coordinator_forecast, description)
        for description in SENSOR_TYPES
    ]
    # Add rain forecast entity only if location support this feature
    if coordinator_rain:
        entities.extend(
            [
                MeteoFranceRainSensor(coordinator_rain, description)
                for description in SENSOR_TYPES_RAIN
            ]
        )
    # Add weather alert entity only if location support this feature
    if coordinator_alert:
        entities.extend(
            [
                MeteoFranceAlertSensor(coordinator_alert, description)
                for description in SENSOR_TYPES_ALERT
            ]
        )
    # Add weather probability entities only if location support this feature
    if coordinator_forecast.data.probability_forecast:
        entities.extend(
            [
                MeteoFranceSensor(coordinator_forecast, description)
                for description in SENSOR_TYPES_PROBABILITY
            ]
        )

    async_add_entities(entities, False)


class MeteoFranceSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Meteo-France sensor."""

    entity_description: MeteoFranceSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: MeteoFranceSensorEntityDescription,
    ) -> None:
        """Initialize the Meteo-France sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        if hasattr(coordinator.data, "position"):
            city_name = coordinator.data.position["name"]
            self._attr_name = f"{city_name} {description.name}"
            self._attr_unique_id = f"{coordinator.data.position['lat']},{coordinator.data.position['lon']}_{description.key}"
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.platform.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.coordinator.name,
        )

    @property
    def native_value(self):
        """Return the state."""
        path = self.entity_description.data_path.split(":")
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

        if self.entity_description.key in ("wind_speed", "wind_gust"):
            # convert API wind speed from m/s to km/h
            value = round(value * 3.6)
        return value


class MeteoFranceRainSensor(MeteoFranceSensor):
    """Representation of a Meteo-France rain sensor."""

    @property
    def native_value(self):
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

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: MeteoFranceSensorEntityDescription,
    ) -> None:
        """Initialize the Meteo-France sensor."""
        super().__init__(coordinator, description)
        dept_code = self.coordinator.data.domain_id
        self._attr_name = f"{dept_code} {description.name}"
        self._attr_unique_id = self._attr_name

    @property
    def native_value(self):
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
