"""Sensor platform of the VARTA Storage integration."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize the integration."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        VartaStorageEntity(coordinator, idx) for idx, ent in enumerate(coordinator.data)
    )


class VartaStorageEntity(CoordinatorEntity, SensorEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = idx

        self._attr_device_info = DeviceInfo(
            configuration_url="http://" + coordinator.config_entry.data["host"],
            identifiers={(DOMAIN, str(coordinator.config_entry.unique_id))},
            manufacturer="VARTA",
            name="VARTA Battery",
        )

        self._attr_unique_id = coordinator.config_entry.unique_id + "-" + self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.coordinator.data[self.idx]["name"]

    @property
    # pylint: disable=overridden-final-method
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.idx]["state"]

    @property
    def device_class(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.idx]["device_class"]

    @property
    def state_class(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.idx]["state_class"]

    @property
    # pylint: disable=overridden-final-method
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the sensor."""
        return self.coordinator.data[self.idx]["unit_of_measurement"]
