"""Sensor checking adc and status values from your ROMY."""

from romy import RomyRobot

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import RomyVacuumCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ROMY vacuum cleaner."""

    coordinator: RomyVacuumCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    binary_sensor_entities = []

    romy_binary_sensor_entitiy_dustbin_present = RomyBinarySensor(
        coordinator, coordinator.romy, None, "Dustbin present", "dustbin"
    )
    if "dustbin" in coordinator.romy.binary_sensors:
        LOGGER.info(
            "Binary sensor Dustbin present found for ROMY %s",
            coordinator.romy.unique_id,
        )
        binary_sensor_entities.append(romy_binary_sensor_entitiy_dustbin_present)

    romy_binary_sensor_entitiy_docked = RomyBinarySensor(
        coordinator,
        coordinator.romy,
        BinarySensorDeviceClass.PRESENCE,
        "Robot docked",
        "dock",
    )
    if "dock" in coordinator.romy.binary_sensors:
        LOGGER.info("Binary Robot docked found for ROMY %s", coordinator.romy.unique_id)
        binary_sensor_entities.append(romy_binary_sensor_entitiy_docked)

    romy_binary_sensor_entitiy_watertank_present = RomyBinarySensor(
        coordinator,
        coordinator.romy,
        BinarySensorDeviceClass.MOISTURE,
        "Watertank present",
        "water_tank",
    )
    if "water_tank" in coordinator.romy.binary_sensors:
        LOGGER.info(
            "Binary sensor Watertank present found for ROMY %s",
            coordinator.romy.unique_id,
        )
        binary_sensor_entities.append(romy_binary_sensor_entitiy_watertank_present)

    romy_binary_sensor_entitiy_watertank_empty = RomyBinarySensor(
        coordinator,
        coordinator.romy,
        BinarySensorDeviceClass.PROBLEM,
        "Watertank empty",
        "water_tank_empty",
    )
    if "water_tank_empty" in coordinator.romy.binary_sensors:
        LOGGER.info(
            "Binary sensor Watertank empty found for ROMY %s",
            coordinator.romy.unique_id,
        )
        binary_sensor_entities.append(romy_binary_sensor_entitiy_watertank_empty)

    async_add_entities(binary_sensor_entities, True)


class RomyBinarySensor(CoordinatorEntity[RomyVacuumCoordinator], BinarySensorEntity):
    """RomyBinarySensor Class."""

    def __init__(
        self,
        coordinator: RomyVacuumCoordinator,
        romy: RomyRobot,
        device_class: BinarySensorDeviceClass | None,
        sensor_name: str,
        device_descriptor: str,
    ) -> None:
        """Initialize ROMYs BinarySensor."""
        super().__init__(coordinator)
        self.romy = romy
        self._attr_unique_id = self.romy.unique_id
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, romy.unique_id)},
            manufacturer="ROMY",
            name=romy.name,
            model=romy.model,
        )
        self._attr_device_class = device_class
        self._sensor_value = False
        self._sensor_name = sensor_name
        self._device_descriptor = device_descriptor

    @property
    def device_descriptor(self) -> str:
        """Return the device_descriptor of this sensor."""
        return self._device_descriptor

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self._device_descriptor}_{self._attr_unique_id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("################ async_update")
        self._sensor_value = self.romy.binary_sensors[self._device_descriptor]
        self.async_write_ha_state()

    # async def async_update(self) -> None:
    #    """Fetch value from the device."""
    #    LOGGER.debug("################ async_update")
    #    self._sensor_value = self.romy.binary_sensors[self._device_descriptor]

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self._sensor_value
