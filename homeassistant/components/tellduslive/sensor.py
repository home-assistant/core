"""Support for Tellstick Net/Telstick Live sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components import sensor
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    UV_INDEX,
    EntityCategory,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TelldusLiveClient, TelldusLiveConfigEntry
from .const import (
    DOMAIN,
    SIGNAL_UPDATE_ENTITY,
    TELLDUS_DISCOVERY_NEW,
    TelldusLiveStatus,
)
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
    config_entry: TelldusLiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tellduslive sensors dynamically."""
    client = config_entry.runtime_data.client
    async_add_entities(
        TelldusLiveDiagnosticSensor(config_entry.entry_id, client, description)
        for description in DIAGNOSTIC_SENSORS
    )

    async def async_discover_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = config_entry.runtime_data.client
        async_add_entities([TelldusLiveSensor(client, device_id)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            TELLDUS_DISCOVERY_NEW.format(sensor.DOMAIN, DOMAIN),
            async_discover_sensor,
        )
    )


@dataclass(frozen=True, kw_only=True)
class TelldusLiveDiagnosticDescription(SensorEntityDescription):
    """Describes a Telldus Live integration diagnostic sensor."""

    value_fn: Callable[[TelldusLiveClient], Any]


DIAGNOSTIC_SENSORS = (
    TelldusLiveDiagnosticDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in TelldusLiveStatus],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.status.value,
    ),
    TelldusLiveDiagnosticDescription(
        key="requests_per_hour",
        translation_key="requests_per_hour",
        native_unit_of_measurement="requests/h",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.requests_last_hour,
    ),
)


class TelldusLiveDiagnosticSensor(SensorEntity):
    """Integration status and API usage of a Telldus Live account."""

    entity_description: TelldusLiveDiagnosticDescription
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
        client: TelldusLiveClient,
        description: TelldusLiveDiagnosticDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._client = client
        self._attr_unique_id = f"{entry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Telldus",
            name="Telldus Live",
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_ENTITY, self.async_write_ha_state
            )
        )

    @property
    @override
    def native_value(self) -> Any:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self._client)


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
    @override
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
        return round(float(self._value))

    @property
    @override
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
    @override
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "-".join(map(str, self._id))
