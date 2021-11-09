"""Support for Tellstick Net/Telstick Live sensors."""
from __future__ import annotations

from homeassistant.components import sensor, tellduslive
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_MILLIMETERS,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRECIPITATION_MILLIMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    UV_INDEX,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .entry import TelldusLiveEntity

SENSOR_TYPE_TEMPERATURE = "temp"
SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_RAINRATE = "rrate"
SENSOR_TYPE_RAINTOTAL = "rtot"
SENSOR_TYPE_WINDDIRECTION = "wdir"
SENSOR_TYPE_WINDAVERAGE = "wavg"
SENSOR_TYPE_WINDGUST = "wgust"
SENSOR_TYPE_UV = "uv"
SENSOR_TYPE_WATT = "watt"
SENSOR_TYPE_LUMINANCE = "lum"
SENSOR_TYPE_DEW_POINT = "dewp"
SENSOR_TYPE_BAROMETRIC_PRESSURE = "barpress"

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    SENSOR_TYPE_TEMPERATURE: SensorEntityDescription(
        key=SENSOR_TYPE_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SENSOR_TYPE_HUMIDITY: SensorEntityDescription(
        key=SENSOR_TYPE_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SENSOR_TYPE_RAINRATE: SensorEntityDescription(
        key=SENSOR_TYPE_RAINRATE,
        name="Rain rate",
        native_unit_of_measurement=PRECIPITATION_MILLIMETERS_PER_HOUR,
        icon="mdi:water",
    ),
    SENSOR_TYPE_RAINTOTAL: SensorEntityDescription(
        key=SENSOR_TYPE_RAINTOTAL,
        name="Rain total",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:water",
    ),
    SENSOR_TYPE_WINDDIRECTION: SensorEntityDescription(
        key=SENSOR_TYPE_WINDDIRECTION,
        name="Wind direction",
    ),
    SENSOR_TYPE_WINDAVERAGE: SensorEntityDescription(
        key=SENSOR_TYPE_WINDAVERAGE,
        name="Wind average",
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
    ),
    SENSOR_TYPE_WINDGUST: SensorEntityDescription(
        key=SENSOR_TYPE_WINDGUST,
        name="Wind gust",
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
    ),
    SENSOR_TYPE_UV: SensorEntityDescription(
        key=SENSOR_TYPE_UV,
        name="UV",
        native_unit_of_measurement=UV_INDEX,
    ),
    SENSOR_TYPE_WATT: SensorEntityDescription(
        key=SENSOR_TYPE_WATT,
        name="Power",
        native_unit_of_measurement=POWER_WATT,
    ),
    SENSOR_TYPE_LUMINANCE: SensorEntityDescription(
        key=SENSOR_TYPE_LUMINANCE,
        name="Luminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
    ),
    SENSOR_TYPE_DEW_POINT: SensorEntityDescription(
        key=SENSOR_TYPE_DEW_POINT,
        name="Dew Point",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SENSOR_TYPE_BAROMETRIC_PRESSURE: SensorEntityDescription(
        key=SENSOR_TYPE_BAROMETRIC_PRESSURE,
        name="Barometric Pressure",
        native_unit_of_measurement="kPa",
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tellduslive sensors dynamically."""

    async def async_discover_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[tellduslive.DOMAIN]
        async_add_entities([TelldusLiveSensor(client, device_id)])

    async_dispatcher_connect(
        hass,
        tellduslive.TELLDUS_DISCOVERY_NEW.format(sensor.DOMAIN, tellduslive.DOMAIN),
        async_discover_sensor,
    )


class TelldusLiveSensor(TelldusLiveEntity, SensorEntity):
    """Representation of a Telldus Live sensor."""

    def __init__(self, client, device_id):
        """Initialize TelldusLiveSensor."""
        super().__init__(client, device_id)
        if desc := SENSOR_TYPES.get(self._type):
            self.entity_description = desc

    @property
    def device_id(self):
        """Return id of the device."""
        return self._id[0]

    @property
    def _type(self):
        """Return the type of the sensor."""
        return self._id[1]

    @property
    def _value(self):
        """Return value of the sensor."""
        return self.device.value(*self._id[1:])

    @property
    def _value_as_temperature(self):
        """Return the value as temperature."""
        return round(float(self._value), 1)

    @property
    def _value_as_luminance(self):
        """Return the value as luminance."""
        return round(float(self._value), 1)

    @property
    def _value_as_humidity(self):
        """Return the value as humidity."""
        return int(round(float(self._value)))

    @property
    def name(self):
        """Return the name of the sensor."""
        quantity_name = (
            self.entity_description.name if hasattr(self, "entity_description") else ""
        )
        return "{} {}".format(super().name, quantity_name or "").strip()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.available:
            return None
        if self._type == SENSOR_TYPE_TEMPERATURE:
            return self._value_as_temperature
        if self._type == SENSOR_TYPE_HUMIDITY:
            return self._value_as_humidity
        if self._type == SENSOR_TYPE_LUMINANCE:
            return self._value_as_luminance
        return self._value

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "{}-{}-{}".format(*self._id)
