"""Support for IoTaWatt Energy monitor."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from iotawattpy.sensor import Sensor

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
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
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt

from .const import (
    ATTR_LAST_UPDATE,
    DOMAIN,
    VOLT_AMPERE_REACTIVE,
    VOLT_AMPERE_REACTIVE_HOURS,
)
from .coordinator import IotawattUpdater

_LOGGER = logging.getLogger(__name__)


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


class IotaWattSensor(update_coordinator.CoordinatorEntity, RestoreEntity, SensorEntity):
    """Defines a IoTaWatt Energy Sensor."""

    entity_description: IotaWattSensorEntityDescription
    _attr_force_update = True

    def __init__(
        self,
        coordinator,
        key,
        entity_description: IotaWattSensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)

        self._key = key
        data = self._sensor_data
        self._accumulating = data.getUnit() == "WattHours" and not data.getFromStart()
        self._accumulated_value = None
        if data.getType() == "Input":
            unit = data.getUnit() + self._name_suffix
            self._attr_unique_id = (
                f"{data.hub_mac_address}-input-{data.getChannel()}-{unit}"
            )
        if self._accumulating:
            self._attr_state_class = STATE_CLASS_TOTAL_INCREASING
        self.entity_description = entity_description

    @property
    def _sensor_data(self) -> Sensor:
        """Return sensor data."""
        return self.coordinator.data["sensors"][self._key]

    @property
    def _name_suffix(self) -> str:
        return ".accumulated" if self._accumulating else ""

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return self._sensor_data.getSourceName() + self._name_suffix

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

        if self._accumulating:
            assert (
                self._accumulated_value is not None
            ), "async_added_to_hass must have been called first"
            self._accumulated_value += float(self._sensor_data.getValue())

        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes of the entity."""
        data = self._sensor_data
        attrs = {"type": data.getType()}
        if attrs["type"] == "Input":
            attrs["channel"] = data.getChannel()
        if self._accumulating:
            attrs[
                ATTR_LAST_UPDATE
            ] = self.coordinator.api.getLastUpdateTime().isoformat()

        return attrs

    async def async_added_to_hass(self):
        """Load the last known state value of the entity if the accumulated type."""
        await super().async_added_to_hass()
        if self._accumulating:
            state = await self.async_get_last_state()
            self._accumulated_value = 0.0
            if state:
                try:
                    self._accumulated_value = float(state.state)
                    if ATTR_LAST_UPDATE in state.attributes:
                        self.coordinator.update_last_run(
                            dt.parse_datetime(state.attributes.get(ATTR_LAST_UPDATE))
                        )
                except (ValueError) as err:
                    _LOGGER.warning("Could not restore last state: %s", err)
            # Force a second update from the iotawatt to ensure that sensors are up to date.
            await self.coordinator.request_refresh()

    @property
    def native_value(self) -> entity.StateType:
        """Return the state of the sensor."""
        if func := self.entity_description.value:
            return func(self._sensor_data.getValue())

        if not self._accumulating:
            return self._sensor_data.getValue()
        if self._accumulated_value is None:
            return None
        return round(self._accumulated_value, 1)
