"""Support for Ezviz Switch sensors."""
import logging
from typing import Callable, List

from pyezviz.constants import DeviceSwitchType

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN, MANUFACTURER
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Ezviz switch based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    switch_entities = []
    supported_switches = []

    for switches in DeviceSwitchType:
        supported_switches.append(switches.value)

    supported_switches = set(supported_switches)

    for idx, camera in enumerate(coordinator.data):
        if camera.get("switches"):
            for switch in camera.get("switches"):
                if switch in supported_switches:
                    switch_entities.append(EzvizSwitch(coordinator, idx, switch))

    async_add_entities(switch_entities)


class EzvizSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Ezviz sensor."""

    def __init__(self, coordinator, idx, switch):
        """Initialize the switch."""
        super().__init__(coordinator)
        self._idx = idx
        self._camera_name = self.coordinator.data[self._idx]["name"]
        self._name = switch
        self._sensor_name = f"{self._camera_name}.{DeviceSwitchType(self._name).name}"
        self._serial = self.coordinator.data[self._idx]["serial"]

    @property
    def name(self):
        """Return the name of the Ezviz switch."""
        return f"{self._camera_name}.{DeviceSwitchType(self._name).name}"

    @property
    def is_on(self):
        """Return the state of the switch."""
        return self.coordinator.data[self._idx]["switches"][self._name]

    @property
    def unique_id(self):
        """Return the unique ID of this switch."""
        return f"{self._serial}_{self._sensor_name}"

    def turn_on(self):
        """Change a device switch on the camera."""
        _LOGGER.debug("Set EZVIZ Switch '%s' to %s", self._name, 1)

        self.coordinator.ezviz_client.switch_status(self._serial, self._name, 1)

    def turn_off(self):
        """Change a device switch on the camera."""
        _LOGGER.debug("Set EZVIZ Switch '%s' to %s", self._name, 0)

        self.coordinator.ezviz_client.switch_status(self._serial, self._name, 0)

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": self.coordinator.data[self._idx]["name"],
            "model": self.coordinator.data[self._idx]["device_sub_category"],
            "manufacturer": MANUFACTURER,
            "sw_version": self.coordinator.data[self._idx]["version"],
        }

    @property
    def device_class(self):
        """Device class for the sensor."""
        return "switch"
