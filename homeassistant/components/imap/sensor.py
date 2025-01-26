"""IMAP sensor support."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_USERNAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ImapConfigEntry
from .const import DOMAIN
from .coordinator import ImapDataUpdateCoordinator

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

IMAP_MAIL_COUNT_DESCRIPTION = SensorEntityDescription(
    key="imap_mail_count",
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
    translation_key="imap_mail_count",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ImapConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Imap sensor."""

    coordinator = entry.runtime_data
    async_add_entities([ImapSensor(coordinator, IMAP_MAIL_COUNT_DESCRIPTION)])


class ImapSensor(CoordinatorEntity[ImapDataUpdateCoordinator], SensorEntity):
    """Representation of an IMAP sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImapDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=f"IMAP ({coordinator.config_entry.data[CONF_USERNAME]})",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        """Return the number of emails found."""
        return self.coordinator.data
