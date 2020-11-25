"""Binary Sensor platform for FireServiceRota integration."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN as FIRESERVICEROTA_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up FireServiceRota binary sensor based on a config entry."""
    coordinator = hass.data[FIRESERVICEROTA_DOMAIN][entry.entry_id]

    async_add_entities([ResponseBinarySensor(coordinator, entry)])


class ResponseBinarySensor(BinarySensorEntity, CoordinatorEntity):
    """Representation of an FireServiceRota sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry):
        """Initialize."""
        super().__init__(coordinator)
        self._unique_id = f"{entry.unique_id}_Duty"

        self._state = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Duty"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:calendar"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this binary sensor."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def is_on(self) -> str:
        """Return the state of the binary sensor."""
        if not self.coordinator.data:
            return

        availability_data = self.coordinator.data
        if "available" in availability_data:
            state = availability_data["available"]
            if state:
                self._state = STATE_ON
            else:
                self._state = STATE_OFF
        else:
            self._state = STATE_OFF

        _LOGGER.debug("Set state of entity 'Duty Binary Sensor' to '%s'", self._state)
        return self._state

    @property
    def device_state_attributes(self):
        """Return available attributes for binary sensor."""
        attr = {}
        if not self.coordinator.data:
            return attr

        data = self.coordinator.data
        attr = {
            key: data[key]
            for key in (
                "start_time",
                "end_time",
                "available",
                "active",
                "assigned_function_ids",
                "skill_ids",
                "type",
                "assigned_function",
            )
            if key in data
        }

        return attr
