"""Support for deCONZ sensors."""
from __future__ import annotations

from collections.abc import Callable, ValuesView
from dataclasses import dataclass
from datetime import datetime

from pydeconz.sensor import (
    AirQuality,
    Consumption,
    Daylight,
    DeconzSensor as PydeconzSensor,
    GenericStatus,
    Humidity,
    LightLevel,
    Power,
    Pressure,
    Switch,
    Temperature,
    Time,
)

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
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
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
    value_fn: Callable[[PydeconzSensor], float | int | str | None]


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
            value_fn=lambda device: device.air_quality,  # type: ignore[no-any-return]
            update_key="airquality",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        DeconzSensorDescription(
            key="air_quality_ppb",
            value_fn=lambda device: device.air_quality_ppb,  # type: ignore[no-any-return]
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
            value_fn=lambda device: device.scaled_consumption,  # type: ignore[no-any-return]
            update_key="consumption",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        )
    ],
    Daylight: [
        DeconzSensorDescription(
            key="status",
            value_fn=lambda device: device.status,  # type: ignore[no-any-return]
            update_key="status",
            icon="mdi:white-balance-sunny",
            entity_registry_enabled_default=False,
        )
    ],
    GenericStatus: [
        DeconzSensorDescription(
            key="status",
            value_fn=lambda device: device.status,  # type: ignore[no-any-return]
            update_key="status",
        )
    ],
    Humidity: [
        DeconzSensorDescription(
            key="humidity",
            value_fn=lambda device: device.scaled_humidity,  # type: ignore[no-any-return]
            update_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        )
    ],
    LightLevel: [
        DeconzSensorDescription(
            key="light_level",
            value_fn=lambda device: device.scaled_light_level,  # type: ignore[no-any-return]
            update_key="lightlevel",
            device_class=SensorDeviceClass.ILLUMINANCE,
            native_unit_of_measurement=LIGHT_LUX,
        )
    ],
    Power: [
        DeconzSensorDescription(
            key="power",
            value_fn=lambda device: device.power,  # type: ignore[no-any-return]
            update_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=POWER_WATT,
        )
    ],
    Pressure: [
        DeconzSensorDescription(
            key="pressure",
            value_fn=lambda device: device.pressure,  # type: ignore[no-any-return]
            update_key="pressure",
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PRESSURE_HPA,
        )
    ],
    Temperature: [
        DeconzSensorDescription(
            key="temperature",
            value_fn=lambda device: device.temperature,  # type: ignore[no-any-return]
            update_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=TEMP_CELSIUS,
        )
    ],
    Time: [
        DeconzSensorDescription(
            key="last_set",
            value_fn=lambda device: device.last_set,  # type: ignore[no-any-return]
            update_key="lastset",
            device_class=SensorDeviceClass.TIMESTAMP,
            state_class=SensorStateClass.TOTAL_INCREASING,
        )
    ],
}

SENSOR_DESCRIPTIONS = [
    DeconzSensorDescription(
        key="battery",
        value_fn=lambda device: device.battery,  # type: ignore[no-any-return]
        suffix="Battery",
        update_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeconzSensorDescription(
        key="secondary_temperature",
        value_fn=lambda device: device.secondary_temperature,  # type: ignore[no-any-return]
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

    battery_handler = DeconzBatteryHandler(gateway)

    @callback
    def async_add_sensor(
        sensors: list[PydeconzSensor]
        | ValuesView[PydeconzSensor] = gateway.api.sensors.values(),
    ) -> None:
        """Add sensors from deCONZ.

        Create DeconzBattery if sensor has a battery attribute.
        Create DeconzSensor if not a battery, switch or thermostat and not a binary sensor.
        """
        entities: list[DeconzSensor] = []

        for sensor in sensors:

            if not gateway.option_allow_clip_sensor and sensor.type.startswith("CLIP"):
                continue

            if sensor.battery is None:
                battery_handler.create_tracker(sensor)

            known_entities = set(gateway.entities[DOMAIN])
            for description in (
                ENTITY_DESCRIPTIONS.get(type(sensor), []) + SENSOR_DESCRIPTIONS
            ):

                if (
                    not hasattr(sensor, description.key)
                    or description.value_fn(sensor) is None
                ):
                    continue

                new_entity = DeconzSensor(sensor, gateway, description)
                if new_entity.unique_id not in known_entities:
                    entities.append(new_entity)

                    if description.key == "battery":
                        battery_handler.remove_tracker(sensor)

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_new_sensor,
            async_add_sensor,
        )
    )

    async_add_sensor(
        [gateway.api.sensors[key] for key in sorted(gateway.api.sensors, key=int)]
    )


class DeconzSensor(DeconzDevice, SensorEntity):
    """Representation of a deCONZ sensor."""

    TYPE = DOMAIN
    _device: PydeconzSensor
    entity_description: DeconzSensorDescription

    def __init__(
        self,
        device: PydeconzSensor,
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
            return dt_util.parse_datetime(
                self.entity_description.value_fn(self._device)  # type: ignore[arg-type]
            )
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


class DeconzSensorStateTracker:
    """Track sensors without a battery state and signal when battery state exist."""

    def __init__(self, sensor: PydeconzSensor, gateway: DeconzGateway) -> None:
        """Set up tracker."""
        self.sensor = sensor
        self.gateway = gateway
        sensor.register_callback(self.async_update_callback)

    @callback
    def close(self) -> None:
        """Clean up tracker."""
        self.sensor.remove_callback(self.async_update_callback)
        self.sensor = None

    @callback
    def async_update_callback(self) -> None:
        """Sensor state updated."""
        if "battery" in self.sensor.changed_keys:
            async_dispatcher_send(
                self.gateway.hass,
                self.gateway.signal_new_sensor,
                [self.sensor],
            )


class DeconzBatteryHandler:
    """Creates and stores trackers for sensors without a battery state."""

    def __init__(self, gateway: DeconzGateway) -> None:
        """Set up battery handler."""
        self.gateway = gateway
        self._trackers: set[DeconzSensorStateTracker] = set()

    @callback
    def create_tracker(self, sensor: PydeconzSensor) -> None:
        """Create new tracker for battery state."""
        for tracker in self._trackers:
            if sensor == tracker.sensor:
                return
        self._trackers.add(DeconzSensorStateTracker(sensor, self.gateway))

    @callback
    def remove_tracker(self, sensor: PydeconzSensor) -> None:
        """Remove tracker of battery state."""
        for tracker in self._trackers:
            if sensor == tracker.sensor:
                tracker.close()
                self._trackers.remove(tracker)
                break
