"""Platform for sensor integration."""

import logging

from laundrify_aio import LaundrifyDevice
from laundrify_aio.exceptions import LaundrifyDeviceException

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaundrifyUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add power sensor for passed config_entry in HA."""

    coordinator: LaundrifyUpdateCoordinator = hass.data[DOMAIN][config.entry_id][
        "coordinator"
    ]

    sensor_entities: list[LaundrifyPowerSensor | LaundrifyEnergySensor] = []
    for device in coordinator.data.values():
        sensor_entities.append(LaundrifyPowerSensor(device))
        sensor_entities.append(LaundrifyEnergySensor(coordinator, device))

    async_add_entities(sensor_entities)


class LaundrifyBaseSensor(SensorEntity):
    """Base class for Laundrify sensors."""

    _attr_has_entity_name = True

    def __init__(self, device: LaundrifyDevice) -> None:
        """Initialize the sensor."""
        self._device = device
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device.id)})
        self._attr_unique_id = f"{device.id}_{self._attr_device_class}"


class LaundrifyPowerSensor(LaundrifyBaseSensor):
    """Representation of a Power sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    async def async_update(self) -> None:
        """Fetch latest power measurement from the device."""
        try:
            power = await self._device.get_power()
        except LaundrifyDeviceException as err:
            _LOGGER.debug("Couldn't load power for %s: %s", self._attr_unique_id, err)
            self._attr_available = False
        else:
            _LOGGER.debug("Retrieved power for %s: %s", self._attr_unique_id, power)
            if power is not None:
                self._attr_available = True
                self._attr_native_value = power


class LaundrifyEnergySensor(
    CoordinatorEntity[LaundrifyUpdateCoordinator], LaundrifyBaseSensor
):
    """Representation of an Energy sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: LaundrifyUpdateCoordinator, device: LaundrifyDevice
    ) -> None:
        """Initialize the sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        LaundrifyBaseSensor.__init__(self, device)

    @property
    def native_value(self) -> float:
        """Return the total energy of the device."""
        device = self.coordinator.data[self._device.id]
        return float(device.totalEnergy)
