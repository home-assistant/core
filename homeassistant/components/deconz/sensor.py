"""Support for deCONZ sensors."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypeVar

from pydeconz.interfaces.sensors import SensorResources
from pydeconz.models.event import EventType
from pydeconz.models.sensor import SensorBase as PydeconzSensorBase
from pydeconz.models.sensor.air_quality import AirQuality
from pydeconz.models.sensor.consumption import Consumption
from pydeconz.models.sensor.daylight import DAYLIGHT_STATUS, Daylight
from pydeconz.models.sensor.generic_status import GenericStatus
from pydeconz.models.sensor.humidity import Humidity
from pydeconz.models.sensor.light_level import LightLevel
from pydeconz.models.sensor.power import Power
from pydeconz.models.sensor.pressure import Pressure
from pydeconz.models.sensor.switch import Switch
from pydeconz.models.sensor.temperature import Temperature
from pydeconz.models.sensor.time import Time

from homeassistant.components.sensor import (
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    CONCENTRATION_PARTS_PER_BILLION,
    ENERGY_KILO_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import ATTR_DARK, ATTR_ON, DOMAIN as DECONZ_DOMAIN
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

_SensorDeviceT = TypeVar("_SensorDeviceT", bound=PydeconzSensorBase)

PROVIDES_EXTRA_ATTRIBUTES = (
    "battery",
    "consumption",
    "daylight_status",
    "humidity",
    "light_level",
    "power",
    "pressure",
    "status",
    "temperature",
)

ATTR_CURRENT = "current"
ATTR_POWER = "power"
ATTR_DAYLIGHT = "daylight"
ATTR_EVENT_ID = "event_id"


@callback
def async_update_unique_id(
    hass: HomeAssistant, unique_id: str, entity_class: DeconzSensor
) -> None:
    """Update unique ID to always have a suffix.

    Introduced with release 2022.9.
    """
    ent_reg = er.async_get(hass)

    new_unique_id = f"{unique_id}-{entity_class.unique_id_suffix}"
    if ent_reg.async_get_entity_id(DOMAIN, DECONZ_DOMAIN, new_unique_id):
        return

    if entity_class.old_unique_id_suffix:
        unique_id = f'{unique_id.split("-", 1)[0]}-{entity_class.old_unique_id_suffix}'

    if entity_id := ent_reg.async_get_entity_id(DOMAIN, DECONZ_DOMAIN, unique_id):
        ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ sensors."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    known_device_entities: dict[str, set[str]] = {
        entity_class.unique_id_suffix: set()
        for entity_class in (
            DeconzBatteryCommonSensor,
            DeconzInternalTemperatureCommonSensor,
        )
        if entity_class.unique_id_suffix is not None
    }

    @callback
    def async_add_sensor(_: EventType, sensor_id: str) -> None:
        """Add sensor from deCONZ."""
        sensor = gateway.api.sensors[sensor_id]
        entities: list[DeconzSensor] = []

        for sensor_type, entity_class in ENTITY_CLASSES:
            if TYPE_CHECKING:
                assert isinstance(entity_class, DeconzSensor)
            no_sensor_data = False
            if (
                not isinstance(sensor, sensor_type)
                or entity_class.unique_id_suffix is not None
                and getattr(sensor, entity_class.unique_id_suffix) is None
            ):
                no_sensor_data = True

            if entity_class in (
                DeconzBatteryCommonSensor,
                DeconzInternalTemperatureCommonSensor,
            ):
                assert entity_class.unique_id_suffix
                if (
                    sensor.type.startswith("CLIP")
                    or (no_sensor_data and entity_class.unique_id_suffix != "battery")
                    or (
                        (unique_id := sensor.unique_id.rsplit("-", 1)[0])
                        in known_device_entities[entity_class.unique_id_suffix]
                    )
                ):
                    continue
                known_device_entities[entity_class.unique_id_suffix].add(unique_id)
                if no_sensor_data and entity_class.unique_id_suffix == "battery":
                    async_update_unique_id(hass, sensor.unique_id, entity_class)
                    DeconzBatteryTracker(sensor_id, gateway, async_add_entities)
                    continue

            if no_sensor_data:
                continue

            async_update_unique_id(hass, sensor.unique_id, entity_class)
            entities.append(entity_class(sensor, gateway))

        async_add_entities(entities)

    gateway.register_platform_add_device_callback(
        async_add_sensor,
        gateway.api.sensors,
    )


class DeconzBatteryTracker:
    """Track sensors without a battery state and add entity when battery state exist."""

    def __init__(
        self,
        sensor_id: str,
        gateway: DeconzGateway,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up tracker."""
        self.sensor = gateway.api.sensors[sensor_id]
        self.gateway = gateway
        self.async_add_entities = async_add_entities
        self.unsubscribe = self.sensor.subscribe(self.async_update_callback)

    @callback
    def async_update_callback(self) -> None:
        """Update the device's state."""
        if "battery" in self.sensor.changed_keys:
            self.unsubscribe()
            self.async_add_entities(
                [DeconzBatteryCommonSensor(self.sensor, self.gateway)]
            )


class DeconzSensor(DeconzDevice[_SensorDeviceT], SensorEntity):
    """Representation of a deCONZ sensor."""

    old_unique_id_suffix = ""
    TYPE = DOMAIN

    def __init__(self, device: _SensorDeviceT, gateway: DeconzGateway) -> None:
        """Initialize deCONZ sensor."""
        super().__init__(device, gateway)

        if (
            self.unique_id_suffix in PROVIDES_EXTRA_ATTRIBUTES
            and self._update_keys is not None
        ):
            self._update_keys.update({"on", "state"})

    @property
    def extra_state_attributes(self) -> dict[str, bool | float | int | str | None]:
        """Return the state attributes of the sensor."""
        attr: dict[str, bool | float | int | str | None] = {}

        if self.unique_id_suffix not in PROVIDES_EXTRA_ATTRIBUTES:
            return attr

        if self._device.on is not None:
            attr[ATTR_ON] = self._device.on

        if self._device.internal_temperature is not None:
            attr[ATTR_TEMPERATURE] = self._device.internal_temperature

        if isinstance(self._device, Consumption):
            attr[ATTR_POWER] = self._device.power

        elif isinstance(self._device, Daylight):
            attr[ATTR_DAYLIGHT] = self._device.daylight

        elif isinstance(self._device, LightLevel):

            if self._device.dark is not None:
                attr[ATTR_DARK] = self._device.dark

            if self._device.daylight is not None:
                attr[ATTR_DAYLIGHT] = self._device.daylight

        elif isinstance(self._device, Power):
            attr[ATTR_CURRENT] = self._device.current
            attr[ATTR_VOLTAGE] = self._device.voltage

        elif isinstance(self._device, Switch):
            for event in self.gateway.events:
                if self._device == event.device:
                    attr[ATTR_EVENT_ID] = event.event_id

        return attr


class DeconzAirQualitySensor(DeconzSensor[AirQuality]):
    """Representation of a deCONZ air quality sensor."""

    unique_id_suffix = "air_quality"
    _update_key = "airquality"

    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.air_quality


class DeconzAirQualityPPBSensor(DeconzSensor[AirQuality]):
    """Representation of a deCONZ air quality PPB sensor."""

    _name_suffix = "PPB"
    unique_id_suffix = "air_quality_ppb"
    old_unique_id_suffix = "ppb"
    _update_key = "airqualityppb"

    _attr_device_class = SensorDeviceClass.AQI
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_BILLION

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.air_quality_ppb


class DeconzConsumptionSensor(DeconzSensor[Consumption]):
    """Representation of a deCONZ consumption sensor."""

    unique_id_suffix = "consumption"
    _update_key = "consumption"

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.scaled_consumption


class DeconzDaylightSensor(DeconzSensor[Daylight]):
    """Representation of a deCONZ daylight sensor."""

    unique_id_suffix = "daylight_status"
    _update_key = "status"

    _attr_icon = "mdi:white-balance-sunny"
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return DAYLIGHT_STATUS[self._device.daylight_status]


class DeconzGenericStatusSensor(DeconzSensor[GenericStatus]):
    """Representation of a deCONZ generic status sensor."""

    unique_id_suffix = "status"
    _update_key = "status"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.status


class DeconzHumiditySensor(DeconzSensor[Humidity]):
    """Representation of a deCONZ humidity sensor."""

    unique_id_suffix = "humidity"
    _update_key = "humidity"

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.scaled_humidity


class DeconzLightLevelSensor(DeconzSensor[LightLevel]):
    """Representation of a deCONZ light level sensor."""

    unique_id_suffix = "light_level"
    _update_key = "lightlevel"

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.scaled_light_level


class DeconzPowerSensor(DeconzSensor[Power]):
    """Representation of a deCONZ power sensor."""

    unique_id_suffix = "power"
    _update_key = "power"

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = POWER_WATT

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.power


class DeconzPressureSensor(DeconzSensor[Pressure]):
    """Representation of a deCONZ pressure sensor."""

    unique_id_suffix = "pressure"
    _update_key = "pressure"

    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PRESSURE_HPA

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.pressure


class DeconzTemperatureSensor(DeconzSensor[Temperature]):
    """Representation of a deCONZ temperature sensor."""

    unique_id_suffix = "temperature"
    _update_key = "temperature"

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.scaled_temperature


class DeconzTimeSensor(DeconzSensor[Time]):
    """Representation of a deCONZ time sensor."""

    unique_id_suffix = "last_set"
    _update_key = "lastset"

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        return dt_util.parse_datetime(self._device.last_set)


class DeconzBatteryCommonSensor(DeconzSensor[SensorResources]):
    """Representation of a deCONZ battery sensor."""

    _name_suffix = "Battery"
    unique_id_suffix = "battery"
    old_unique_id_suffix = "battery"
    _update_key = "battery"

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.battery


class DeconzInternalTemperatureCommonSensor(DeconzSensor[SensorResources]):
    """Representation of a deCONZ internal temperature sensor."""

    _name_suffix = "Temperature"
    unique_id_suffix = "internal_temperature"
    old_unique_id_suffix = "temperature"
    _update_key = "temperature"

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.internal_temperature


ENTITY_CLASSES = (
    (AirQuality, DeconzAirQualitySensor),
    (AirQuality, DeconzAirQualityPPBSensor),
    (Consumption, DeconzConsumptionSensor),
    (Daylight, DeconzDaylightSensor),
    (GenericStatus, DeconzGenericStatusSensor),
    (Humidity, DeconzHumiditySensor),
    (LightLevel, DeconzLightLevelSensor),
    (Power, DeconzPowerSensor),
    (Pressure, DeconzPressureSensor),
    (Temperature, DeconzTemperatureSensor),
    (Time, DeconzTimeSensor),
    (PydeconzSensorBase, DeconzBatteryCommonSensor),
    (PydeconzSensorBase, DeconzInternalTemperatureCommonSensor),
)
