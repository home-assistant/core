"""Binary sensors for the Ablago integration."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    AblagoConfigEntry,
    AblagoCounterCoordinator,
    AblagoHealthCoordinator,
)
from .entity import AblagoEntity

PARALLEL_UPDATES = 0

NEW_MAIL = BinarySensorEntityDescription(
    key="has_new_mail", translation_key="has_new_mail"
)
CONNECTIVITY = BinarySensorEntityDescription(
    key="connectivity",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AblagoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    async_add_entities(
        [
            AblagoNewMailBinarySensor(entry.runtime_data.counters, NEW_MAIL),
            AblagoConnectivityBinarySensor(entry.runtime_data.health, CONNECTIVITY),
        ]
    )


class AblagoNewMailBinarySensor(
    AblagoEntity[AblagoCounterCoordinator], BinarySensorEntity
):
    """On while there is new mail for the person, the simple trigger for a lamp or a notification."""

    @property
    @override
    def is_on(self) -> bool:
        """Return True if there is new mail."""
        return self.coordinator.data.neue_post > 0


class AblagoConnectivityBinarySensor(
    AblagoEntity[AblagoHealthCoordinator], BinarySensorEntity
):
    """On while Ablago runs and its database answers."""

    @property
    @override
    def is_on(self) -> bool:
        """Return True if Ablago is reachable and ready."""
        return self.coordinator.data is not None and self.coordinator.data.ok
