"""IMAP sensor support."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ImapPollingDataUpdateCoordinator, ImapPushDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Imap sensor."""

    coordinator: ImapPushDataUpdateCoordinator | ImapPollingDataUpdateCoordinator = (
        hass.data[DOMAIN][entry.entry_id]
    )

    async_add_entities([ImapSensor(coordinator)])


class ImapSensor(
    CoordinatorEntity[ImapPushDataUpdateCoordinator | ImapPollingDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of an IMAP sensor."""

    _attr_icon = "mdi:email-outline"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImapPushDataUpdateCoordinator | ImapPollingDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
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
