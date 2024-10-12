"""Support for Tellstick Net/Telstick Live sensors."""

from __future__ import annotations

from homeassistant.components import sensor
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    UV_INDEX,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TELLDUS_DISCOVERY_NEW
from .entity import TelldusLiveEntity

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
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_TYPE_HUMIDITY: SensorEntityDescription(
        key=SENSOR_TYPE_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_TYPE_RAINRATE: SensorEntityDescription(
        key=SENSOR_TYPE_RAINRATE,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    SENSOR_TYPE_RAINTOTAL: SensorEntityDescription(
        key=SENSOR_TYPE_RAINTOTAL,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SENSOR_TYPE_WINDDIRECTION: SensorEntityDescription(
        key=SENSOR_TYPE_WINDDIRECTION,
        translation_key="wind_direction",
    ),
    SENSOR_TYPE_WINDAVERAGE: SensorEntityDescription(
        key=SENSOR_TYPE_WINDAVERAGE,
        translation_key="wind_average",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_TYPE_WINDGUST: SensorEntityDescription(
        key=SENSOR_TYPE_WINDGUST,
        translation_key="wind_gust",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_TYPE_UV: SensorEntityDescription(
        key=SENSOR_TYPE_UV,
        translation_key="uv",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_TYPE_WATT: SensorEntityDescription(
        key=SENSOR_TYPE_WATT,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_TYPE_LUMINANCE: SensorEntityDescription(
        key=SENSOR_TYPE_LUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_TYPE_DEW_POINT: SensorEntityDescription(
        key=SENSOR_TYPE_DEW_POINT,
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_TYPE_BAROMETRIC_PRESSURE: SensorEntityDescription(
        key=SENSOR_TYPE_BAROMETRIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up tellduslive sensors dynamically."""

    async def async_discover_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[DOMAIN]
        async_add_entities([TelldusLiveSensor(client, device_id)])

    async_dispatcher_connect(
        hass,
        TELLDUS_DISCOVERY_NEW.format(sensor.DOMAIN, DOMAIN),
        async_discover_sensor,
    )


class TelldusLiveSensor(TelldusLiveEntity, SensorEntity):
    """Representation of a Telldus Live sensor."""

    def __init__(self, client, device_id):
        """Initialize TelldusLiveSensor."""
        super().__init__(client, device_id)
        if desc := SENSOR_TYPES.get(self._type):
            self.entity_description = desc
        else:
            self._attr_name = None

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
        return "-".join(map(str, self._id))
