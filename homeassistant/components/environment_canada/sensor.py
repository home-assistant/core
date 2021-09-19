"""Sensors for Environment Canada (EC)."""
import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_NAME,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure

from . import ECBaseEntity
from .const import AQHI_SENSOR, DEFAULT_NAME, DOMAIN, SENSOR_TYPES

ALERTS = [
    ("advisories", "Advisory", "mdi:bell-alert"),
    ("endings", "Ending", "mdi:alert-circle-check"),
    ("statements", "Statement", "mdi:bell-alert"),
    ("warnings", "Warning", "mdi:alert-octagon"),
    ("watches", "Watch", "mdi:alert"),
]
MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=5)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the EC weather platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["weather_coordinator"]
    async_add_entities(
        ECSensor(
            coordinator, config_entry.data, description, hass.config.units.is_metric
        )
        for description in SENSOR_TYPES
    )
    async_add_entities(
        ECAlertSensor(coordinator, config_entry.data, alert) for alert in ALERTS
    )

    aqhi_coordinator = hass.data[DOMAIN][config_entry.entry_id]["aqhi_coordinator"]
    async_add_entities(
        [ECSensor(aqhi_coordinator, config_entry.data, AQHI_SENSOR, True)]
    )


class ECSensor(ECBaseEntity, SensorEntity):
    """An EC Sensor Entity."""

    def __init__(self, coordinator, config, description, is_metric):
        """Initialise the platform with a data instance."""
        name = f"{config.get(CONF_NAME, DEFAULT_NAME)} {description.name}"
        super().__init__(coordinator, config, name)

        self._entity_description = description
        self._is_metric = is_metric
        if is_metric:
            self._attr_native_unit_of_measurement = (
                description.native_unit_of_measurement
            )
        else:
            self._attr_native_unit_of_measurement = description.unit_convert
        self._attr_device_class = description.device_class
        self._unique_id_tail = self._entity_description.key

    @property
    def native_value(self):
        """Return the state."""
        key = self._entity_description.key
        value = self._coordinator.data.current if key == "aqhi" else self.get_value(key)

        if value is None:
            return None

        if key == "pressure":
            value = int(value * 10)  # Convert kPa to hPa
        elif key == "tendency":
            value = value.title()
        elif isinstance(value, str) and len(value) > 254:
            value = value[:254]

        if self._is_metric:
            return value

        unit_of_measurement = self._entity_description.unit_convert
        if unit_of_measurement in [SPEED_MILES_PER_HOUR, LENGTH_MILES]:
            value = round(convert_distance(value, LENGTH_KILOMETERS, LENGTH_MILES), 2)
        elif unit_of_measurement == LENGTH_INCHES:
            value = round(convert_distance(value, LENGTH_MILLIMETERS, LENGTH_INCHES), 2)
        elif unit_of_measurement == PRESSURE_INHG:
            value = round(convert_pressure(value, PRESSURE_HPA, PRESSURE_INHG), 2)
        elif unit_of_measurement == TEMP_CELSIUS:
            value = round(value, 1)
        elif unit_of_measurement == PERCENTAGE:
            value = round(value)
        return value

    @property
    def icon(self):
        """Return the icon."""
        return self._entity_description.icon


class ECAlertSensor(ECBaseEntity, SensorEntity):
    """An EC Sensor Entity for Alerts."""

    def __init__(self, coordinator, config, alert_name):
        """Initialise the platform with a data instance."""
        name = f"{config.get(CONF_NAME, DEFAULT_NAME)} {alert_name[1]} Alerts"
        super().__init__(coordinator, config, name)

        self._alert_name = alert_name
        self._alert_attrs = None
        self._unique_id_tail = self._alert_name[0]

    @property
    def native_value(self):
        """Return the state."""
        value = self._coordinator.data.alerts.get(self._alert_name[0], {}).get("value")

        self._alert_attrs = {}
        for index, alert in enumerate(value, start=1):
            self._alert_attrs[f"alert {index}"] = alert.get("title")
            self._alert_attrs[f"alert_time {index}"] = alert.get("date")

        return len(value)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._alert_attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._alert_name[2]
