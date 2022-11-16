"""Support for IoTaWatt Energy monitor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from iotawattpy.sensor import Sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity, entity_registry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
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
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    "Hz": IotaWattSensorEntityDescription(
        "Hz",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    "PF": IotaWattSensorEntityDescription(
        "PF",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        value=lambda value: value * 100,
        entity_registry_enabled_default=False,
    ),
    "Watts": IotaWattSensorEntityDescription(
        "Watts",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "WattHours": IotaWattSensorEntityDescription(
        "WattHours",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
    ),
    "VA": IotaWattSensorEntityDescription(
        "VA",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    "VAR": IotaWattSensorEntityDescription(
        "VAR",
        native_unit_of_measurement=VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    "VARh": IotaWattSensorEntityDescription(
        "VARh",
        native_unit_of_measurement=VOLT_AMPERE_REACTIVE_HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    "Volts": IotaWattSensorEntityDescription(
        "Volts",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator: IotawattUpdater = hass.data[DOMAIN][config_entry.entry_id]
    created = set()

    @callback
    def _create_entity(key: str) -> IotaWattSensor:
        """Create a sensor entity."""
        created.add(key)
        data = coordinator.data["sensors"][key]
        description = ENTITY_DESCRIPTION_KEY_MAP.get(
            data.getUnit(), IotaWattSensorEntityDescription("base_sensor")
        )
        if data.getUnit() == "WattHours" and not data.getFromStart():
            return IotaWattAccumulatingSensor(
                coordinator=coordinator, key=key, entity_description=description
            )

        return IotaWattSensor(
            coordinator=coordinator,
            key=key,
            entity_description=description,
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
        async_add_entities(entities)

    coordinator.async_add_listener(new_data_received)


class IotaWattSensor(CoordinatorEntity[IotawattUpdater], SensorEntity):
    """Defines a IoTaWatt Energy Sensor."""

    entity_description: IotaWattSensorEntityDescription

    def __init__(
        self,
        coordinator: IotawattUpdater,
        key: str,
        entity_description: IotaWattSensorEntityDescription,
    ) -> None:
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
    def device_info(self) -> entity.DeviceInfo:
        """Return device info."""
        return entity.DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._sensor_data.hub_mac_address)},
            manufacturer="IoTaWatt",
            model="IoTaWatt",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._key not in self.coordinator.data["sensors"]:
            if self._attr_unique_id:
                entity_registry.async_get(self.hass).async_remove(self.entity_id)
            else:
                self.hass.async_create_task(self.async_remove())
            return

        if (begin := self._sensor_data.getBegin()) and (
            last_reset := dt.parse_datetime(begin)
        ):
            self._attr_last_reset = last_reset

        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the extra state attributes of the entity."""
        data = self._sensor_data
        attrs = {"type": data.getType()}
        if attrs["type"] == "Input":
            attrs["channel"] = data.getChannel()

        return attrs

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if func := self.entity_description.value:
            return func(self._sensor_data.getValue())

        return self._sensor_data.getValue()


class IotaWattAccumulatingSensor(IotaWattSensor, RestoreEntity):
    """Defines a IoTaWatt Accumulative Energy (High Accuracy) Sensor."""

    def __init__(
        self,
        coordinator: IotawattUpdater,
        key: str,
        entity_description: IotaWattSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, key, entity_description)

        if self._attr_unique_id is not None:
            self._attr_unique_id += ".accumulated"

        self._accumulated_value: float | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        assert (
            self._accumulated_value is not None
        ), "async_added_to_hass must have been called first"
        self._accumulated_value += float(self._sensor_data.getValue())

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self._accumulated_value is None:
            return None
        return round(self._accumulated_value, 1)

    async def async_added_to_hass(self) -> None:
        """Load the last known state value of the entity if the accumulated type."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        self._accumulated_value = 0.0
        if state:
            try:
                # Previous value could be `unknown` if the connection didn't originally
                # complete.
                self._accumulated_value = float(state.state)
            except (ValueError) as err:
                _LOGGER.warning("Could not restore last state: %s", err)
            else:
                if ATTR_LAST_UPDATE in state.attributes:
                    last_run = dt.parse_datetime(state.attributes[ATTR_LAST_UPDATE])
                    if last_run is not None:
                        self.coordinator.update_last_run(last_run)
        # Force a second update from the iotawatt to ensure that sensors are up to date.
        await self.coordinator.async_request_refresh()

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return f"{self._sensor_data.getSourceName()} Accumulated"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the extra state attributes of the entity."""
        attrs = super().extra_state_attributes

        assert (
            self.coordinator.api is not None
            and self.coordinator.api.getLastUpdateTime() is not None
        )
        attrs[ATTR_LAST_UPDATE] = self.coordinator.api.getLastUpdateTime().isoformat()

        return attrs
