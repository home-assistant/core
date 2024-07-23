"""Support for Rflink sensors."""

from __future__ import annotations

from typing import Any

from rflink.parser import PACKET_FIELDS, UNITS
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_DEVICES,
    CONF_NAME,
    CONF_SENSOR_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UV_INDEX,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_ALIASES,
    CONF_AUTOMATIC_ADD,
    DATA_DEVICE_REGISTER,
    DATA_ENTITY_LOOKUP,
    EVENT_KEY_ID,
    EVENT_KEY_SENSOR,
    EVENT_KEY_UNIT,
    SIGNAL_AVAILABILITY,
    SIGNAL_HANDLE_EVENT,
    TMP_ENTITY,
    RflinkDevice,
)

SENSOR_TYPES = (
    # check new descriptors against PACKET_FIELDS & UNITS from rflink.parser
    SensorEntityDescription(
        key="average_windspeed",
        name="Average windspeed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
    ),
    SensorEntityDescription(
        key="barometric_pressure",
        name="Barometric pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        key="co2_air_quality",
        name="CO2 air quality",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    SensorEntityDescription(
        key="command",
        name="Command",
        icon="mdi:text",
    ),
    SensorEntityDescription(
        key="current_phase_1",
        name="Current phase 1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SensorEntityDescription(
        key="current_phase_2",
        name="Current phase 2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SensorEntityDescription(
        key="current_phase_3",
        name="Current phase 3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SensorEntityDescription(
        key="distance",
        name="Distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
    ),
    SensorEntityDescription(
        key="doorbell_melody",
        name="Doorbell melody",
        icon="mdi:bell",
    ),
    SensorEntityDescription(
        key="firmware",
        name="Firmware",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="hardware",
        name="Hardware",
        icon="mdi:chip",
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="humidity_status",
        name="Humidity status",
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="kilowatt",
        name="Kilowatt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    SensorEntityDescription(
        key="light_intensity",
        name="Light intensity",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    SensorEntityDescription(
        key="meter_value",
        name="Meter value",
        icon="mdi:counter",
    ),
    SensorEntityDescription(
        key="noise_level",
        name="Noise level",
        icon="mdi:bell-alert",
    ),
    SensorEntityDescription(
        key="rain_rate",
        name="Rain rate",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    ),
    SensorEntityDescription(
        key="revision",
        name="Revision",
        icon="mdi:information",
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="total_rain",
        name="Total rain",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
    ),
    SensorEntityDescription(
        key="uv_intensity",
        name="UV intensity",
        icon="mdi:sunglasses",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UV_INDEX,
    ),
    SensorEntityDescription(
        key="version",
        name="Version",
        icon="mdi:information",
    ),
    SensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SensorEntityDescription(
        key="watt",
        name="Watt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="weather_forecast",
        name="Weather forecast",
        icon="mdi:weather-cloudy-clock",
    ),
    SensorEntityDescription(
        key="windchill",
        name="Wind chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="winddirection",
        name="Wind direction",
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key="windgusts",
        name="Wind gusts",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
    ),
    SensorEntityDescription(
        key="windspeed",
        name="Wind speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
    ),
    SensorEntityDescription(
        key="windtemp",
        name="Wind temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
)

SENSOR_TYPES_DICT = {desc.key: desc for desc in SENSOR_TYPES}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_AUTOMATIC_ADD, default=True): cv.boolean,
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Required(CONF_SENSOR_TYPE): cv.string,
                    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
                    vol.Optional(CONF_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                }
            )
        },
    },
    extra=vol.ALLOW_EXTRA,
)


def lookup_unit_for_sensor_type(sensor_type):
    """Get unit for sensor type.

    Async friendly.
    """
    field_abbrev = {v: k for k, v in PACKET_FIELDS.items()}

    return UNITS.get(field_abbrev.get(sensor_type))


def devices_from_config(domain_config):
    """Parse configuration and add Rflink sensor devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        device = RflinkSensor(device_id, **config)
        devices.append(device)

    return devices


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Rflink platform."""
    async_add_entities(devices_from_config(config))

    async def add_new_device(event):
        """Check if device is known, otherwise create device entity."""
        device_id = event[EVENT_KEY_ID]

        device = RflinkSensor(
            device_id,
            event[EVENT_KEY_SENSOR],
            event[EVENT_KEY_UNIT],
            initial_event=event,
        )
        # Add device entity
        async_add_entities([device])

    if config[CONF_AUTOMATIC_ADD]:
        hass.data[DATA_DEVICE_REGISTER][EVENT_KEY_SENSOR] = add_new_device


class RflinkSensor(RflinkDevice, SensorEntity):
    """Representation of a Rflink sensor."""

    def __init__(
        self,
        device_id: str,
        sensor_type: str,
        unit_of_measurement: str | None = None,
        initial_event=None,
        **kwargs: Any,
    ) -> None:
        """Handle sensor specific args and super init."""
        self._sensor_type = sensor_type
        self._unit_of_measurement = unit_of_measurement
        if sensor_type in SENSOR_TYPES_DICT:
            self.entity_description = SENSOR_TYPES_DICT[sensor_type]
        elif not unit_of_measurement:
            self._unit_of_measurement = lookup_unit_for_sensor_type(sensor_type)

        super().__init__(device_id, initial_event=initial_event, **kwargs)

    def _handle_event(self, event):
        """Domain specific event handler."""
        self._state = event["value"]

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        # Remove temporary bogus entity_id if added
        tmp_entity = TMP_ENTITY.format(self._device_id)
        if (
            tmp_entity
            in self.hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_SENSOR][self._device_id]
        ):
            self.hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_SENSOR][
                self._device_id
            ].remove(tmp_entity)

        # Register id and aliases
        self.hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_SENSOR][self._device_id].append(
            self.entity_id
        )
        if self._aliases:
            for _id in self._aliases:
                self.hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_SENSOR][_id].append(
                    self.entity_id
                )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_AVAILABILITY, self._availability_callback
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_HANDLE_EVENT.format(self.entity_id),
                self.handle_event_callback,
            )
        )

        # Process the initial event now that the entity is created
        if self._initial_event:
            self.handle_event_callback(self._initial_event)

    @property
    def native_unit_of_measurement(self):
        """Return measurement unit."""
        if self._unit_of_measurement:
            return self._unit_of_measurement
        if hasattr(self, "entity_description"):
            return self.entity_description.native_unit_of_measurement
        return None

    @property
    def native_value(self):
        """Return value."""
        return self._state
