"""Support for Verisure Smartplugs."""
from __future__ import annotations

from time import monotonic
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VerisureDataUpdateCoordinator
from .const import CONF_SMARTPLUGS, DOMAIN


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[Entity], bool], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure switch platform."""
    coordinator = hass.data[DOMAIN]

    if not int(coordinator.config.get(CONF_SMARTPLUGS, 1)):
        return

    add_entities(
        [
            VerisureSmartplug(coordinator, device_label)
            for device_label in coordinator.get("$.smartPlugs[*].deviceLabel")
        ]
    )


class VerisureSmartplug(CoordinatorEntity, SwitchEntity):
    """Representation of a Verisure smartplug."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize the Verisure device."""
        super().__init__(coordinator)
        self._device_label = device_id
        self._change_timestamp = 0
        self._state = False

    @property
    def name(self) -> str:
        """Return the name or location of the smartplug."""
        return self.coordinator.get_first(
            "$.smartPlugs[?(@.deviceLabel == '%s')].area", self._device_label
        )

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        if monotonic() - self._change_timestamp < 10:
            return self._state
        self._state = (
            self.coordinator.get_first(
                "$.smartPlugs[?(@.deviceLabel == '%s')].currentState",
                self._device_label,
            )
            == "ON"
        )
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.get_first(
                "$.smartPlugs[?(@.deviceLabel == '%s')]", self._device_label
            )
            is not None
        )

    def turn_on(self, **kwargs) -> None:
        """Set smartplug status on."""
        self.coordinator.session.set_smartplug_state(self._device_label, True)
        self._state = True
        self._change_timestamp = monotonic()

    def turn_off(self, **kwargs) -> None:
        """Set smartplug status off."""
        self.coordinator.session.set_smartplug_state(self._device_label, False)
        self._state = False
        self._change_timestamp = monotonic()
