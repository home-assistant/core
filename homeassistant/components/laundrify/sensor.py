"""Platform for sensor integration."""

import logging

from laundrify_aio import LaundrifyDevice
from laundrify_aio.exceptions import LaundrifyDeviceException

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaundrifyUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

POWER_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="power",
    device_class=SensorDeviceClass.POWER,
    native_unit_of_measurement=UnitOfPower.WATT,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
    has_entity_name=True,
)

ENERGY_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="energy",
    device_class=SensorDeviceClass.ENERGY,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    state_class=SensorStateClass.TOTAL,
    suggested_display_precision=2,
    has_entity_name=True,
)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
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


class LaundrifyPowerSensor(SensorEntity):
    """Representation of a Power sensor."""

    def __init__(self, device: LaundrifyDevice) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.entity_description = POWER_SENSOR_DESCRIPTION
        self._device = device
        self._attr_device_info = {"identifiers": {(DOMAIN, device.id)}}
        self._attr_unique_id = f"{device.id}_{POWER_SENSOR_DESCRIPTION.key}"

    async def async_update(self) -> None:
        """Fetch latest power measurement from the device."""
        try:
            power = await self._device.get_power()
            _LOGGER.debug("%s: %s", self._attr_unique_id, power)
            if power is not None:
                self._attr_available = True
                self._attr_native_value = power
            else:
                raise LaundrifyDeviceException("Received invalid power value (None).")
        except LaundrifyDeviceException as err:
            _LOGGER.debug("Couldn't load power for %s: %s", self._attr_unique_id, err)
            self._attr_available = False


class LaundrifyEnergySensor(
    CoordinatorEntity[LaundrifyUpdateCoordinator], SensorEntity
):
    """Representation of an Energy sensor."""

    def __init__(
        self, coordinator: LaundrifyUpdateCoordinator, device: LaundrifyDevice
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = ENERGY_SENSOR_DESCRIPTION
        self._device = device
        self._attr_device_info = {"identifiers": {(DOMAIN, device.id)}}
        self._attr_unique_id = f"{device.id}_{ENERGY_SENSOR_DESCRIPTION.key}"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return float(self._device.totalEnergy) / 1000

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._device = self.coordinator.data[self._device.id]
        self.async_write_ha_state()
