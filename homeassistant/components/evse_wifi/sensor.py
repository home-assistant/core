"""Platform for EVSE Sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    evse = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = EvseCoordinator(hass, evse)

    new_devices = [
        VehicleStateSensor(coordinator, evse),
        VehicleStateTextSensor(coordinator, evse),
    ]
    new_devices.append(MaxCurrentSensor(coordinator, evse))
    new_devices.append(ActualPowerSensor(coordinator, evse))
    new_devices.append(DurationSensor(coordinator, evse))
    new_devices.append(LastActionUserSensor(coordinator, evse))
    new_devices.append(LastActionUidSensor(coordinator, evse))
    new_devices.append(EnergySensor(coordinator, evse))
    new_devices.append(MilageSensor(coordinator, evse))
    new_devices.append(MeterReadingSensor(coordinator, evse))
    new_devices.append(CurrentP1Sensor(coordinator, evse))
    new_devices.append(CurrentP2Sensor(coordinator, evse))
    new_devices.append(CurrentP3Sensor(coordinator, evse))
    async_add_entities(new_devices)

    await coordinator.async_config_entry_first_refresh()


class EvseCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, evse):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="EVSE Data",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=evse.interval),
        )
        self.evse = evse

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                return await self.evse.get_parameters()
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("EVSE Coordinator update Exception: %s", exception)


class VehicleStateSensor(CoordinatorEntity, SensorEntity):
    """Vehicle State Sensor."""

    def __init__(self, coordinator, evse):
        """Init Vehicle State Sensor."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_vehicle_state"
        self._attr_name = f"{self.evse.name} Vehicle State"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_vehicle_state()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class VehicleStateTextSensor(CoordinatorEntity, SensorEntity):
    """Vehicle State Sensor."""

    def __init__(self, coordinator, evse):
        """Init Vehicle State Sensor."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_vehicle_state_text"
        self._attr_name = f"{self.evse.name} Vehicle State Text"
        self.attr_device_class = SensorDeviceClass.ENUM
        self.attr_options = (
            [
                "Ready",
                "Detected",
                "Charging",
                "Unknown",
            ],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_vehicle_state()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self._state == 0:
            return "Ready"
        if self._state == 1:
            return "Detected"
        if self._state == 3:
            return "Charging"
        return "Unknown"


class MaxCurrentSensor(CoordinatorEntity, SensorEntity):
    """Max Current Sensor. The Current that is set in the EVSE Settings."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_max_current"
        self._attr_name = f"{self.evse.name} MAX Current"
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_max_current()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class ActualPowerSensor(CoordinatorEntity, SensorEntity):
    """Actual Power Sensor."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_actual_power"
        self._attr_name = f"{self.evse.name} Actual Power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_actual_power()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class DurationSensor(CoordinatorEntity, SensorEntity):
    """Charge Duration Sensor."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_charge_duration"
        self._attr_name = f"{self.evse.name} Charge Duration"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_duration()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor as seconds."""
        if self._state is None:
            return 0
        return self._state / 1000  # convert to seconds


class LastActionUserSensor(CoordinatorEntity, SensorEntity):
    """Last Action User Sensor."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_last_action_user"
        self._attr_name = f"{self.evse.name} Last Action User"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_last_action_user()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class LastActionUidSensor(CoordinatorEntity, SensorEntity):
    """Last Action UID Sensor."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_last_action_uid"
        self._attr_name = f"{self.evse.name} Last Action Uid"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_last_action_uid()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class EnergySensor(CoordinatorEntity, SensorEntity):
    """charged energy of the current charging process in kWh Sensor."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_energy"
        self._attr_name = f"{self.evse.name} Energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_energy()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class MilageSensor(CoordinatorEntity, SensorEntity):
    """charged energy in km."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_mileage"
        self._attr_name = f"{self.evse.name} Mileage"
        self._attr_device_class = SensorDeviceClass.DISTANCE
        self._attr_native_unit_of_measurement = UnitOfLength.KILOMETERS

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_milage()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class MeterReadingSensor(CoordinatorEntity, SensorEntity):
    """actual meter reading in kWh."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_meter_reading"
        self._attr_name = f"{self.evse.name} Meter Reading"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_meter_reading()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class CurrentP1Sensor(CoordinatorEntity, SensorEntity):
    """actual current phase 1 in Ampere Sensor."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_current_p1"
        self._attr_name = f"{self.evse.name} Current P1"
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_current_p1()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class CurrentP2Sensor(CoordinatorEntity, SensorEntity):
    """actual current phase 2 in Ampere Sensor."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_current_p2"
        self._attr_name = f"{self.evse.name} Current P2"
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_current_p2()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state


class CurrentP3Sensor(CoordinatorEntity, SensorEntity):
    """actual current phase 3 in Ampere Sensor."""

    def __init__(self, coordinator, evse):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.evse = evse
        self._state = None
        self._attr_unique_id = f"{self.evse.name}_current_p3"
        self._attr_name = f"{self.evse.name} Current P3"
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.evse.get_current_p3()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state
