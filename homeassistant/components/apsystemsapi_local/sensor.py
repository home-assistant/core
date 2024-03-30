"""The read-only sensors for APsystems local API integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ApSystemsDataCoordinator

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default="solar"): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = config["COORDINATOR"]

    sensors = [
        PowerSensorTotal(
            coordinator,
            device_name=config[CONF_NAME],
            sensor_name="Total Power",
            sensor_id="total_power",
        ),
        PowerSensorTotalP1(
            coordinator,
            device_name=config[CONF_NAME],
            sensor_name="Power P1",
            sensor_id="total_power_p1",
        ),
        PowerSensorTotalP2(
            coordinator,
            device_name=config[CONF_NAME],
            sensor_name="Power P2",
            sensor_id="total_power_p2",
        ),
        LifetimeEnergy(
            coordinator,
            device_name=config[CONF_NAME],
            sensor_name="Lifetime Production",
            sensor_id="lifetime_production",
        ),
        LifetimeEnergyP1(
            coordinator,
            device_name=config[CONF_NAME],
            sensor_name="Lifetime Production P1",
            sensor_id="lifetime_production_p1",
        ),
        LifetimeEnergyP2(
            coordinator,
            device_name=config[CONF_NAME],
            sensor_name="Lifetime Production P2",
            sensor_id="lifetime_production_p2",
        ),
        TodayEnergy(
            coordinator,
            device_name=config[CONF_NAME],
            sensor_name="Today Production",
            sensor_id="today_production",
        ),
        TodayEnergyP1(
            coordinator,
            device_name=config[CONF_NAME],
            sensor_name="Today Production P1",
            sensor_id="today_production_p1",
        ),
        TodayEnergyP2(
            coordinator,
            device_name=config[CONF_NAME],
            sensor_name="Today Production P2",
            sensor_id="today_production_p2",
        ),
    ]

    add_entities(sensors)


class BaseSensor(CoordinatorEntity, SensorEntity):
    """Representation of an APsystem sensor."""

    def __init__(
        self,
        coordinator: ApSystemsDataCoordinator,
        device_name: str,
        sensor_name: str,
        sensor_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state: int | None = None
        self._device_name = device_name
        self._sensor_name = sensor_name
        self._sensor_id = sensor_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device_name} {self._sensor_name}"

    @property  # type: ignore[misc]
    def state(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self) -> str | None:
        """Get the sensor's unique id."""
        return f"apsystemsapi_{self._device_name}_{self._sensor_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Get the DeviceInfo."""
        return DeviceInfo(
            identifiers={("apsystemsapi_local", self._device_name)},
            name=self._device_name,
            manufacturer="APsystems",
            model="EZ1-M",
        )


class BasePowerSensor(BaseSensor):
    """Base Power Sensor, not used directly."""

    _device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT


class PowerSensorTotal(BasePowerSensor):
    """Represents PowerSensorTotal."""

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.coordinator.data.p1 + self.coordinator.data.p2  # type: ignore[attr-defined]
        self.async_write_ha_state()


class PowerSensorTotalP1(BasePowerSensor):
    """Represents PowerSensorTotal for Panel 1."""

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.coordinator.data.p1  # type: ignore[attr-defined]
        self.async_write_ha_state()


class PowerSensorTotalP2(BasePowerSensor):
    """Represents PowerSensorTotal for Panel 2."""

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.coordinator.data.p2  # type: ignore[attr-defined]
        self.async_write_ha_state()


class BaseEnergySensor(BaseSensor):
    """Base Energy Sensor, not used directly."""

    _device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY


class LifetimeEnergy(BaseEnergySensor):
    """Returns all-time producion of inverter."""

    _attr_state_class = SensorStateClass.TOTAL

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.coordinator.data.te1 + self.coordinator.data.te2  # type: ignore[attr-defined]
        self.async_write_ha_state()


class LifetimeEnergyP1(BaseEnergySensor):
    """Returns all-time producion of inverter for Panel 1."""

    _attr_state_class = SensorStateClass.TOTAL

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.coordinator.data.te1  # type: ignore[attr-defined]
        self.async_write_ha_state()


class LifetimeEnergyP2(BaseEnergySensor):
    """Returns all-time producion of inverter for Panel 2."""

    _attr_state_class = SensorStateClass.TOTAL

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.coordinator.data.te2  # type: ignore[attr-defined]
        self.async_write_ha_state()


class TodayEnergy(BaseEnergySensor):
    """Returns today's producion of inverter."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.coordinator.data.e1 + self.coordinator.data.e2  # type: ignore[attr-defined]
        self.async_write_ha_state()


class TodayEnergyP1(BaseEnergySensor):
    """Returns today's producion of inverter for Panel 1."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.coordinator.data.e1  # type: ignore[attr-defined]
        self.async_write_ha_state()


class TodayEnergyP2(BaseEnergySensor):
    """Returns today's producion of inverter for Panel 2."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.coordinator.data.e2  # type: ignore[attr-defined]
        self.async_write_ha_state()
