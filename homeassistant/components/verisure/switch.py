"""Support for Verisure Smartplugs."""
from __future__ import annotations

from time import monotonic
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SMARTPLUGS, DOMAIN
from .coordinator import VerisureDataUpdateCoordinator


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[CoordinatorEntity]], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure switch platform."""
    coordinator = hass.data[DOMAIN]

    if not int(coordinator.config.get(CONF_SMARTPLUGS, 1)):
        return

    add_entities(
        [
            VerisureSmartplug(coordinator, serial_number)
            for serial_number in coordinator.data["smart_plugs"]
        ]
    )


class VerisureSmartplug(CoordinatorEntity, SwitchEntity):
    """Representation of a Verisure smartplug."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the Verisure device."""
        super().__init__(coordinator)
        self.serial_number = serial_number
        self._change_timestamp = 0
        self._state = False

    @property
    def name(self) -> str:
        """Return the name or location of the smartplug."""
        return self.coordinator.data["smart_plugs"][self.serial_number]["area"]

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

    def turn_off(self, **kwargs) -> None:
        """Set smartplug status off."""
        self.coordinator.verisure.set_smartplug_state(self.serial_number, False)
        self._state = False
        self._change_timestamp = monotonic()
