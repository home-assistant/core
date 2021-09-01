"""Support for IoTaWatt Energy monitor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from iotawattpy.sensor import Sensor

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
)
from homeassistant.core import callback
from homeassistant.helpers import entity, entity_registry, update_coordinator
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN, VOLT_AMPERE_REACTIVE, VOLT_AMPERE_REACTIVE_HOURS
from .coordinator import IotawattUpdater


@dataclass
class IotaWattSensorEntityDescription(SensorEntityDescription):
    """Class describing IotaWatt sensor entities."""

    value: Callable | None = None


ENTITY_DESCRIPTION_KEY_MAP: dict[str, IotaWattSensorEntityDescription] = {
    "Amps": IotaWattSensorEntityDescription(
        "Amps",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_CURRENT,
        entity_registry_enabled_default=False,
    ),
    "Hz": IotaWattSensorEntityDescription(
        "Hz",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    "PF": IotaWattSensorEntityDescription(
        "PF",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_POWER_FACTOR,
        value=lambda value: value * 100,
        entity_registry_enabled_default=False,
    ),
    "Watts": IotaWattSensorEntityDescription(
        "Watts",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_POWER,
    ),
    "WattHours": IotaWattSensorEntityDescription(
        "WattHours",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    "VA": IotaWattSensorEntityDescription(
        "VA",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    "VAR": IotaWattSensorEntityDescription(
        "VAR",
        native_unit_of_measurement=VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    "VARh": IotaWattSensorEntityDescription(
        "VARh",
        native_unit_of_measurement=VOLT_AMPERE_REACTIVE_HOURS,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    "Volts": IotaWattSensorEntityDescription(
        "Volts",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_VOLTAGE,
        entity_registry_enabled_default=False,
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    coordinator: IotawattUpdater = hass.data[DOMAIN][config_entry.entry_id]
    created = set()

    @callback
    def _create_entity(key: str) -> IotaWattSensor:
        """Create a sensor entity."""
        created.add(key)
        return IotaWattSensor(
            coordinator=coordinator,
            key=key,
            mac_address=coordinator.data["sensors"][key].hub_mac_address,
            name=coordinator.data["sensors"][key].getName(),
            entity_description=ENTITY_DESCRIPTION_KEY_MAP.get(
                coordinator.data["sensors"][key].getUnit(),
                IotaWattSensorEntityDescription("base_sensor"),
            ),
        )

    async_add_entities(_create_entity(key) for key in coordinator.data["sensors"])

    @callback
    def new_data_received():
        """Check for new sensors."""
        entities = [
            _create_entity(key)
            for key in coordinator.data["sensors"]
            if key not in created
        ]
        if entities:
            async_add_entities(entities)

    coordinator.async_add_listener(new_data_received)


class IotaWattSensor(update_coordinator.CoordinatorEntity, SensorEntity):
    """Defines a IoTaWatt Energy Sensor."""

    entity_description: IotaWattSensorEntityDescription
    _attr_force_update = True

    def __init__(
        self,
        coordinator,
        key,
        mac_address,
        name,
        entity_description: IotaWattSensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)

        self._key = key
        data = self._sensor_data
        if data.getType() == "Input":
            self._attr_unique_id = (
                f"{data.hub_mac_address}-input-{data.getChannel()}-{data.getUnit()}"
            )
        self.entity_description = entity_description

    @property
    def _sensor_data(self) -> Sensor:
        """Return sensor data."""
        return self.coordinator.data["sensors"][self._key]

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return self._sensor_data.getName()

    @property
    def device_info(self) -> entity.DeviceInfo | None:
        """Return device info."""
        return {
            "connections": {
                (CONNECTION_NETWORK_MAC, self._sensor_data.hub_mac_address)
            },
            "manufacturer": "IoTaWatt",
            "model": "IoTaWatt",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._key not in self.coordinator.data["sensors"]:
            if self._attr_unique_id:
                entity_registry.async_get(self.hass).async_remove(self.entity_id)
            else:
                self.hass.async_create_task(self.async_remove())
            return

        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes of the entity."""
        data = self._sensor_data
        attrs = {"type": data.getType()}
        if attrs["type"] == "Input":
            attrs["channel"] = data.getChannel()

        return attrs

    @property
    def native_value(self) -> entity.StateType:
        """Return the state of the sensor."""
        if func := self.entity_description.value:
            return func(self._sensor_data.getValue())

        return self._sensor_data.getValue()
