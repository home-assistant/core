"""Support for Verisure sensors."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VerisureDataUpdateCoordinator
from .const import CONF_HYDROMETERS, CONF_MOUSE, CONF_THERMOMETERS, DOMAIN


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[Entity], bool], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure platform."""
    coordinator = hass.data[DOMAIN]

    sensors = []
    if int(coordinator.config.get(CONF_THERMOMETERS, 1)):
        sensors.extend(
            [
                VerisureThermometer(coordinator, device_label)
                for device_label in coordinator.get(
                    "$.climateValues[?(@.temperature)].deviceLabel"
                )
            ]
        )

    if int(coordinator.config.get(CONF_HYDROMETERS, 1)):
        sensors.extend(
            [
                VerisureHygrometer(coordinator, device_label)
                for device_label in coordinator.get(
                    "$.climateValues[?(@.humidity)].deviceLabel"
                )
            ]
        )

    if int(coordinator.config.get(CONF_MOUSE, 1)):
        sensors.extend(
            [
                VerisureMouseDetection(coordinator, device_label)
                for device_label in coordinator.get(
                    "$.eventCounts[?(@.deviceType=='MOUSE1')].deviceLabel"
                )
            ]
        )

    add_entities(sensors)


class VerisureThermometer(CoordinatorEntity, Entity):
    """Representation of a Verisure thermometer."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, device_label: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_label = device_label

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return (
            self.coordinator.get_first(
                "$.climateValues[?(@.deviceLabel=='%s')].deviceArea", self._device_label
            )
            + " temperature"
        )

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self.coordinator.get_first(
            "$.climateValues[?(@.deviceLabel=='%s')].temperature", self._device_label
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.get_first(
                "$.climateValues[?(@.deviceLabel=='%s')].temperature",
                self._device_label,
            )
            is not None
        )

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return TEMP_CELSIUS


class VerisureHygrometer(CoordinatorEntity, Entity):
    """Representation of a Verisure hygrometer."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, device_label: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_label = device_label

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return (
            self.coordinator.get_first(
                "$.climateValues[?(@.deviceLabel=='%s')].deviceArea", self._device_label
            )
            + " humidity"
        )

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self.coordinator.get_first(
            "$.climateValues[?(@.deviceLabel=='%s')].humidity", self._device_label
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.get_first(
                "$.climateValues[?(@.deviceLabel=='%s')].humidity", self._device_label
            )
            is not None
        )

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return PERCENTAGE


class VerisureMouseDetection(CoordinatorEntity, Entity):
    """Representation of a Verisure mouse detector."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, device_label: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_label = device_label

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return (
            self.coordinator.get_first(
                "$.eventCounts[?(@.deviceLabel=='%s')].area", self._device_label
            )
            + " mouse"
        )

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self.coordinator.get_first(
            "$.eventCounts[?(@.deviceLabel=='%s')].detections", self._device_label
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.get_first(
                "$.eventCounts[?(@.deviceLabel=='%s')]", self._device_label
            )
            is not None
        )

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return "Mice"
