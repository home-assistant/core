"""Support for Verisure Smartplugs."""
from __future__ import annotations

from time import monotonic
from typing import Any, Callable, Literal

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import CONF_SMARTPLUGS, HUB as hub


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[Entity], bool], None],
    discovery_info: dict[str, Any] | None = None,
) -> None | Literal[False]:
    """Set up the Verisure switch platform."""
    if not int(hub.config.get(CONF_SMARTPLUGS, 1)):
        return False

    hub.update_overview()
    switches = [
        VerisureSmartplug(device_label)
        for device_label in hub.get("$.smartPlugs[*].deviceLabel")
    ]

    add_entities(switches)


class VerisureSmartplug(SwitchEntity):
    """Representation of a Verisure smartplug."""

    def __init__(self, device_id: str):
        """Initialize the Verisure device."""
        self._device_label = device_id
        self._change_timestamp = 0
        self._state = False

    @property
    def name(self) -> str:
        """Return the name or location of the smartplug."""
        return hub.get_first(
            "$.smartPlugs[?(@.deviceLabel == '%s')].area", self._device_label
        )

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        if monotonic() - self._change_timestamp < 10:
            return self._state
        self._state = (
            hub.get_first(
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
            hub.get_first("$.smartPlugs[?(@.deviceLabel == '%s')]", self._device_label)
            is not None
        )

    def turn_on(self, **kwargs) -> None:
        """Set smartplug status on."""
        hub.session.set_smartplug_state(self._device_label, True)
        self._state = True
        self._change_timestamp = monotonic()

    def turn_off(self, **kwargs) -> None:
        """Set smartplug status off."""
        hub.session.set_smartplug_state(self._device_label, False)
        self._state = False
        self._change_timestamp = monotonic()

    # pylint: disable=no-self-use
    def update(self) -> None:
        """Get the latest date of the smartplug."""
        hub.update_overview()
