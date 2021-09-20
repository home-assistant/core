"""Support for Verisure Smartplugs."""
from __future__ import annotations

from time import monotonic

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_GIID, DOMAIN
from .coordinator import VerisureDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Verisure alarm control panel from a config entry."""
    coordinator: VerisureDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        VerisureSmartplug(coordinator, serial_number)
        for serial_number in coordinator.data["smart_plugs"]
    )


class VerisureSmartplug(CoordinatorEntity, SwitchEntity):
    """Representation of a Verisure smartplug."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the Verisure device."""
        super().__init__(coordinator)

        self._attr_name = coordinator.data["smart_plugs"][serial_number]["area"]
        self._attr_unique_id = serial_number

        self.serial_number = serial_number
        self._change_timestamp = 0
        self._state = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        area = self.coordinator.data["smart_plugs"][self.serial_number]["area"]
        return {
            "name": area,
            "suggested_area": area,
            "manufacturer": "Verisure",
            "model": "SmartPlug",
            "identifiers": {(DOMAIN, self.serial_number)},
            "via_device": (DOMAIN, self.coordinator.entry.data[CONF_GIID]),
        }

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        if monotonic() - self._change_timestamp < 10:
            return self._state
        self._state = (
            self.coordinator.data["smart_plugs"][self.serial_number]["currentState"]
            == "ON"
        )
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.serial_number in self.coordinator.data["smart_plugs"]
        )

    def turn_on(self, **kwargs) -> None:
        """Set smartplug status on."""
        self.coordinator.verisure.set_smartplug_state(self.serial_number, True)
        self._state = True
        self._change_timestamp = monotonic()
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Set smartplug status off."""
        self.coordinator.verisure.set_smartplug_state(self.serial_number, False)
        self._state = False
        self._change_timestamp = monotonic()
        self.schedule_update_ha_state()
