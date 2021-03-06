"""Support for Verisure binary sensors."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import CONF_DOOR_WINDOW, HUB as hub


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[Entity], bool], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure binary sensors."""
    sensors = []
    hub.update_overview()

    if int(hub.config.get(CONF_DOOR_WINDOW, 1)):
        sensors.extend(
            [
                VerisureDoorWindowSensor(device_label)
                for device_label in hub.get(
                    "$.doorWindow.doorWindowDevice[*].deviceLabel"
                )
            ]
        )

    sensors.extend([VerisureEthernetStatus()])
    add_entities(sensors)


class VerisureDoorWindowSensor(BinarySensorEntity):
    """Representation of a Verisure door window sensor."""

    def __init__(self, device_label: str):
        """Initialize the Verisure door window sensor."""
        self._device_label = device_label

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return hub.get_first(
            "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].area",
            self._device_label,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return (
            hub.get_first(
                "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].state",
                self._device_label,
            )
            == "OPEN"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            hub.get_first(
                "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')]",
                self._device_label,
            )
            is not None
        )

    # pylint: disable=no-self-use
    def update(self) -> None:
        """Update the state of the sensor."""
        hub.update_overview()


class VerisureEthernetStatus(BinarySensorEntity):
    """Representation of a Verisure VBOX internet status."""

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return "Verisure Ethernet status"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return hub.get_first("$.ethernetConnectedNow")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return hub.get_first("$.ethernetConnectedNow") is not None

    # pylint: disable=no-self-use
    def update(self) -> None:
        """Update the state of the sensor."""
        hub.update_overview()

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CONNECTIVITY
