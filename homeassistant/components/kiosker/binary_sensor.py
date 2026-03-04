"""Support for Kiosker binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KioskerConfigEntry
from .coordinator import KioskerData, KioskerDataUpdateCoordinator
from .entity import KioskerEntity

# Limit concurrent updates to prevent overwhelming the API
PARALLEL_UPDATES = 3


@dataclass(frozen=True, kw_only=True)
class KioskerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Kiosker binary sensor entity."""

    value_fn: Callable[[KioskerData], bool]


BINARY_SENSORS: tuple[KioskerBinarySensorEntityDescription, ...] = (
    KioskerBinarySensorEntityDescription(
        key="blackoutState",
        translation_key="blackout_state",
        value_fn=lambda x: x.blackout.visible if x.blackout else False,
    ),
    KioskerBinarySensorEntityDescription(
        key="screensaverVisibility",
        translation_key="screensaver_visibility",
        value_fn=lambda x: x.screensaver.visible if x.screensaver else False,
    ),
    KioskerBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda x: x.status.battery_state in ("Charging", "Fully Charged"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KioskerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kiosker binary sensors based on a config entry."""
    coordinator = entry.runtime_data

    # Create all binary sensors - they will handle missing data gracefully
    async_add_entities(
        KioskerBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class KioskerBinarySensor(KioskerEntity, BinarySensorEntity):
    """Representation of a Kiosker binary sensor."""

    entity_description: KioskerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: KioskerDataUpdateCoordinator,
        description: KioskerBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, description)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for blackout state sensor."""
        if not self.coordinator.data or self.entity_description.key != "blackoutState":
            return None

        blackout_data = self.coordinator.data.blackout
        if blackout_data is None:
            return None

        return {
            key: getattr(blackout_data, key)
            for key in blackout_data.__dataclass_fields__
            if not key.startswith("_")
        }
