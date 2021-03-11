"""Support for Verisure binary sensors."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_SAFETY,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CONF_DOOR_WINDOW, DOMAIN, VerisureDataUpdateCoordinator


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[Entity], bool], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure binary sensors."""
    coordinator = hass.data[DOMAIN]

    sensors = [VerisureEthernetStatus(coordinator), VerisureFirmwareUpdate(coordinator)]

    if int(coordinator.config.get(CONF_DOOR_WINDOW, 1)):
        sensors.extend(
            [
                VerisureDoorWindowSensor(coordinator, device_label)
                for device_label in coordinator.get(
                    "$.doorWindow.doorWindowDevice[*].deviceLabel"
                )
            ]
        )

    add_entities(sensors)


class VerisureDoorWindowSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Verisure door window sensor."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, device_label: str
    ) -> None:
        """Initialize the Verisure door window sensor."""
        super().__init__(coordinator)
        self._device_label = device_label

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return self.coordinator.get_first(
            "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].area",
            self._device_label,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return (
            self.coordinator.get_first(
                "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].state",
                self._device_label,
            )
            == "OPEN"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.get_first(
                "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')]",
                self._device_label,
            )
            is not None
        )


class VerisureEthernetStatus(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Verisure VBOX internet status."""

    coordinator: VerisureDataUpdateCoordinator

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return "Verisure Ethernet status"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.coordinator.get_first("$.ethernetConnectedNow")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.get_first("$.ethernetConnectedNow") is not None

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CONNECTIVITY


class VerisureFirmwareUpdate(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Verisure firmware."""

    coordinator: VerisureDataUpdateCoordinator

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return "Verisure Firmware update"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.coordinator.is_upgradeable()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.is_upgradeable() is not None

    # pylint: disable=no-self-use
    async def async_update(self) -> None:
        """Update the state of the sensor."""
        await self.coordinator.update_firmware_status()

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SAFETY

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True
