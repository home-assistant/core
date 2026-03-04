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
from .coordinator import KioskerDataUpdateCoordinator
from .entity import KioskerEntity

# Limit concurrent updates to prevent overwhelming the API
PARALLEL_UPDATES = 3


@dataclass(frozen=True, kw_only=True)
class KioskerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Kiosker binary sensor entity."""

    value_fn: Callable[[Any], bool]


BINARY_SENSORS: tuple[KioskerBinarySensorEntityDescription, ...] = (
    KioskerBinarySensorEntityDescription(
        key="blackoutState",
        translation_key="blackout_state",
        value_fn=lambda x: hasattr(x, "visible") and x.visible,
    ),
    KioskerBinarySensorEntityDescription(
        key="screensaverVisibility",
        translation_key="screensaver_visibility",
        value_fn=lambda x: hasattr(x, "visible") and x.visible,
    ),
    KioskerBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda x: (
            x.battery_state in ("Charging", "Fully Charged")
            if hasattr(x, "battery_state")
            else False
        ),
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
        if not self.coordinator.data:
            return None

        data_source = None

        if self.entity_description.key == "blackoutState":
            data_source = self.coordinator.data.blackout
        elif self.entity_description.key == "screensaverVisibility":
            data_source = self.coordinator.data.screensaver
        elif self.entity_description.key == "charging":
            data_source = self.coordinator.data.status

        if data_source is not None:
            return self.entity_description.value_fn(data_source)
        return False

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
