"""Definition of Picnic sensors."""

from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ADDRESS, ATTRIBUTION, CONF_COORDINATOR, DOMAIN, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up Picnic sensor entries."""
    picnic_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    # Fetch initial data so we have data when entities subscribe
    await picnic_coordinator.async_refresh()
    if not picnic_coordinator.last_update_success:
        raise PlatformNotReady()

    # Add an entity for each sensor type
    async_add_entities(
        PicnicSensor(picnic_coordinator, config_entry, sensor_type, props)
        for sensor_type, props in SENSOR_TYPES.items()
    )

    return True


class PicnicSensor(CoordinatorEntity):
    """The CoordinatorEntity subclass representing Picnic sensors."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        config_entry: ConfigEntry,
        sensor_type,
        properties,
    ):
        """Init a Picnic sensor."""
        super().__init__(coordinator)

        self.sensor_type = sensor_type
        self.properties = properties
        self.entity_id = f"sensor.picnic_{sensor_type}"
        self._service_unique_id = config_entry.unique_id

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit this state is expressed in."""
        return self.properties.get("unit")

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._service_unique_id}.{self.sensor_type}"

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._to_capitalized_name(self.sensor_type)

    @property
    def state(self) -> StateType:
        """Return the state of the entity."""
        try:
            data_set = self.coordinator.data.get(self.properties["data_type"])
            return self.properties["state"](data_set)
        except (IndexError, KeyError):
            return None

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self.properties.get("class")

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return self.properties["icon"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.state is not None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self.properties.get("default_enabled", False)

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def extra_state_attributes(self):
        """Return the sensor specific state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._service_unique_id)},
            "manufacturer": "Picnic",
            "model": self._service_unique_id,
            "name": f"Picnic: {self.coordinator.data[ADDRESS]}",
            "entry_type": "service",
        }

    @staticmethod
    def _to_capitalized_name(name: str) -> str:
        return name.replace("_", " ").capitalize()
