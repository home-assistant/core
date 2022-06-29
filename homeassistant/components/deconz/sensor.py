"""Support for deCONZ sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pydeconz.interfaces.sensors import SensorResources
from pydeconz.models.event import EventType
from pydeconz.models.sensor.air_quality import AirQuality
from pydeconz.models.sensor.consumption import Consumption
from pydeconz.models.sensor.daylight import Daylight
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
    SensorEntityDescription,
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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import ATTR_DARK, ATTR_ON
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

PROVIDES_EXTRA_ATTRIBUTES = (
    "battery",
    "consumption",
    "status",
    "humidity",
    "light_level",
    "power",
    "pressure",
    "temperature",
)

ATTR_CURRENT = "current"
ATTR_POWER = "power"
ATTR_DAYLIGHT = "daylight"
ATTR_EVENT_ID = "event_id"


@dataclass
class DeconzSensorDescriptionMixin:
    """Required values when describing secondary sensor attributes."""

    update_key: str
    value_fn: Callable[[SensorResources], float | int | str | None]


@dataclass
class DeconzSensorDescription(
    SensorEntityDescription,
    DeconzSensorDescriptionMixin,
):
    """Class describing deCONZ binary sensor entities."""

    suffix: str = ""


ENTITY_DESCRIPTIONS = {
    AirQuality: [
        DeconzSensorDescription(
            key="air_quality",
            value_fn=lambda device: device.air_quality
            if isinstance(device, AirQuality)
            else None,
            update_key="airquality",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        DeconzSensorDescription(
            key="air_quality_ppb",
            value_fn=lambda device: device.air_quality_ppb
            if isinstance(device, AirQuality)
            else None,
            suffix="PPB",
            update_key="airqualityppb",
            device_class=SensorDeviceClass.AQI,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        ),
    ],
    Consumption: [
        DeconzSensorDescription(
            key="consumption",
            value_fn=lambda device: device.scaled_consumption
            if isinstance(device, Consumption) and isinstance(device.consumption, int)
            else None,
            update_key="consumption",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        )
    ],
    Daylight: [
        DeconzSensorDescription(
            key="status",
            value_fn=lambda device: device.status
            if isinstance(device, Daylight)
            else None,
            update_key="status",
            icon="mdi:white-balance-sunny",
            entity_registry_enabled_default=False,
        )
    ],
    GenericStatus: [
        DeconzSensorDescription(
            key="status",
            value_fn=lambda device: device.status
            if isinstance(device, GenericStatus)
            else None,
            update_key="status",
        )
    ],
    Humidity: [
        DeconzSensorDescription(
            key="humidity",
            value_fn=lambda device: device.scaled_humidity
            if isinstance(device, Humidity) and isinstance(device.humidity, int)
            else None,
            update_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        )
    ],
    LightLevel: [
        DeconzSensorDescription(
            key="light_level",
            value_fn=lambda device: device.scaled_light_level
            if isinstance(device, LightLevel) and isinstance(device.light_level, int)
            else None,
            update_key="lightlevel",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=LIGHT_LUX,
        )
    ],
    Power: [
        DeconzSensorDescription(
            key="power",
            value_fn=lambda device: device.power if isinstance(device, Power) else None,
            update_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=POWER_WATT,
        )
    ],
    Pressure: [
        DeconzSensorDescription(
            key="pressure",
            value_fn=lambda device: device.pressure
            if isinstance(device, Pressure)
            else None,
            update_key="pressure",
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PRESSURE_HPA,
        )
    ],
    Temperature: [
        DeconzSensorDescription(
            key="temperature",
            value_fn=lambda device: device.scaled_temperature
            if isinstance(device, Temperature) and isinstance(device.temperature, int)
            else None,
            update_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=TEMP_CELSIUS,
        )
    ],
    Time: [
        DeconzSensorDescription(
            key="last_set",
            value_fn=lambda device: device.last_set
            if isinstance(device, Time)
            else None,
            update_key="lastset",
            device_class=SensorDeviceClass.TIMESTAMP,
            state_class=SensorStateClass.TOTAL_INCREASING,
        )
    ],
}


SENSOR_DESCRIPTIONS = [
    DeconzSensorDescription(
        key="battery",
        value_fn=lambda device: device.battery,
        suffix="Battery",
        update_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeconzSensorDescription(
        key="secondary_temperature",
        value_fn=lambda device: device.secondary_temperature,
        suffix="Temperature",
        update_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ sensors."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_sensor(_: EventType, sensor_id: str) -> None:
        """Add sensor from deCONZ."""
        sensor = gateway.api.sensors[sensor_id]
        entities: list[DeconzSensor] = []

        if not gateway.option_allow_clip_sensor and sensor.type.startswith("CLIP"):
            return

        if sensor.battery is None and not sensor.type.startswith("CLIP"):
            DeconzBatteryTracker(sensor_id, gateway, async_add_entities)

        known_entities = set(gateway.entities[DOMAIN])

        for description in (
            ENTITY_DESCRIPTIONS.get(type(sensor), []) + SENSOR_DESCRIPTIONS
        ):
            if (
                not hasattr(sensor, description.key)
                or description.value_fn(sensor) is None
            ):
                continue

            entity = DeconzSensor(sensor, gateway, description)
            if entity.unique_id not in known_entities:
                entities.append(entity)

        async_add_entities(entities)

    gateway.register_platform_add_device_callback(
        async_add_sensor,
        gateway.api.sensors,
    )

    @callback
    def async_reload_clip_sensors() -> None:
        """Load clip sensor sensors from deCONZ."""
        for sensor_id, sensor in gateway.api.sensors.items():
            if sensor.type.startswith("CLIP"):
                async_add_sensor(EventType.ADDED, sensor_id)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_reload_clip_sensors,
            async_reload_clip_sensors,
        )
    )


class DeconzSensor(DeconzDevice, SensorEntity):
    """Representation of a deCONZ sensor."""

    TYPE = DOMAIN
    _device: SensorResources
    entity_description: DeconzSensorDescription

    def __init__(
        self,
        device: SensorResources,
        gateway: DeconzGateway,
        description: DeconzSensorDescription,
    ) -> None:
        """Initialize deCONZ sensor."""
        self.entity_description = description
        super().__init__(device, gateway)

        if description.suffix:
            self._attr_name = f"{device.name} {description.suffix}"

        self._update_keys = {description.update_key, "reachable"}
        if self.entity_description.key in PROVIDES_EXTRA_ATTRIBUTES:
            self._update_keys.update({"on", "state"})

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        if (
            self.entity_description.key == "battery"
            and self._device.manufacturer == "Danfoss"
            and self._device.model_id
            in [
                "0x8030",
                "0x8031",
                "0x8034",
                "0x8035",
            ]
        ):
            return f"{super().unique_id}-battery"
        if self.entity_description.suffix:
            return f"{self.serial}-{self.entity_description.suffix.lower()}"
        return super().unique_id

    @callback
    def async_update_callback(self) -> None:
        """Update the sensor's state."""
        if self._device.changed_keys.intersection(self._update_keys):
            super().async_update_callback()

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        if self.entity_description.device_class is SensorDeviceClass.TIMESTAMP:
            value = self.entity_description.value_fn(self._device)
            assert isinstance(value, str)
            return dt_util.parse_datetime(value)
        return self.entity_description.value_fn(self._device)

    @property
    def extra_state_attributes(self) -> dict[str, bool | float | int | str | None]:
        """Return the state attributes of the sensor."""
        attr: dict[str, bool | float | int | str | None] = {}

        if self.entity_description.key not in PROVIDES_EXTRA_ATTRIBUTES:
            return attr

        if self._device.on is not None:
            attr[ATTR_ON] = self._device.on

        if self._device.secondary_temperature is not None:
            attr[ATTR_TEMPERATURE] = self._device.secondary_temperature

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
        self.unsub = self.sensor.subscribe(self.async_update_callback)

    @callback
    def async_update_callback(self) -> None:
        """Update the device's state."""
        if "battery" in self.sensor.changed_keys:
            self.unsub()
            known_entities = set(self.gateway.entities[DOMAIN])
            entity = DeconzSensor(self.sensor, self.gateway, SENSOR_DESCRIPTIONS[0])
            if entity.unique_id not in known_entities:
                self.async_add_entities([entity])
