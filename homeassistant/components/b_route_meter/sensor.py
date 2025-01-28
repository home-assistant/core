"""Sensor platform for B-Route Smart Meter.

Defines the sensor entities that read E7/E8/E9/EA/EB data from
the B-route meter using a DataUpdateCoordinator.

"""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEVICE_NAME,
    DEVICE_UNIQUE_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="e7_power",
        name="B-Route Instantaneous Power",
        icon="mdi:flash",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="e8_current",
        name="B-Route Instantaneous Current",
        icon="mdi:current-ac",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="e9_voltage",
        name="B-Route Instantaneous Voltage",
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ea_forward",
        name="B-Route Cumulative Forward",
        icon="mdi:gauge",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="eb_reverse",
        name="B-Route Cumulative Reverse",
        icon="mdi:gauge",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator = entry.runtime_data
    _LOGGER.debug("Setting up B-Route meter sensor platform")
    await coordinator.async_config_entry_first_refresh()

    sensors = [BRouteSensorEntity(entry, description) for description in SENSOR_TYPES]

    async_add_entities(sensors)


class BRouteSensorEntity(SensorEntity):
    """B-Route sensor entity referencing a SensorEntityDescription.

    We store a reference to the DataUpdateCoordinator and a SensorEntityDescription,
    and we get the current sensor value from coordinator.data.
    """

    def __init__(
        self,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        self._coordinator = config_entry.runtime_data
        self.entity_description = description
        self._attr_unique_id = f"b_route_{description.key}"
        self._last_state = None
        self._last_timestamp = None
        _LOGGER.debug(
            "Setting up B-Route sensor entity for %s", self.entity_description.key
        )

    @property
    def should_poll(self) -> bool:
        """Disable polling, because DataUpdateCoordinator handles updates."""
        return False

    @property
    def available(self) -> bool:
        """Is sensor available."""
        return self._coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra state attributes."""
        if self.entity_description.key in ["ea_forward", "eb_reverse"]:
            data = self._coordinator.data
            timestamp_key = f"{self.entity_description.key}_timestamp"

            if data and timestamp_key in data:
                self._last_timestamp = data[timestamp_key]

            if self._last_timestamp:
                return {
                    "last_update": self._last_timestamp,
                }
        return {}

    @property
    def native_value(self) -> float | None:
        """Current sensor reading."""
        data = self._coordinator.data
        _LOGGER.debug(
            "Getting value for %s, data: %s", self.entity_description.key, data
        )
        if not data:
            return None
        # The "key" in description matches the dict key in data
        value = data.get(self.entity_description.key)
        if value is None:
            return self._last_state
        self._last_state = value
        return value

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, DEVICE_UNIQUE_ID)},
            "name": DEVICE_NAME,
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
        }

    async def async_added_to_hass(self) -> None:
        """Register update listener when entity is added."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_remove_listener(self) -> None:
        """Remove the listener."""
        self._coordinator.async_remove_listener(self.async_write_ha_state)
