"""Support for Kiosker binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KioskerConfigEntry
from .coordinator import KioskerData
from .entity import KioskerEntity

# These entities rely on the shared data coordinator instead of per-entity polling.
PARALLEL_UPDATES = 0


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
        key="screensaverState",
        translation_key="screensaver_state",
        value_fn=lambda x: x.screensaver.visible if x.screensaver else False,
    ),
    KioskerBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda x: (
            (x.status.battery_state or "").casefold() in ("charging", "fully charged")
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

    async_add_entities(
        KioskerBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class KioskerBinarySensor(KioskerEntity, BinarySensorEntity):
    """Representation of a Kiosker binary sensor."""

    entity_description: KioskerBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
