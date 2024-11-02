"""Watergate Base Entity Definition."""

from dataclasses import dataclass

from watergate_local_api import WatergateLocalApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WatergateDataCoordinator

type WatergateConfigEntry = ConfigEntry[WatergateData]


class WatergateEntity(CoordinatorEntity[WatergateDataCoordinator]):
    """Define a base Watergate entity."""

    def __init__(
        self,
        coordinator: WatergateDataCoordinator,
        entry: WatergateConfigEntry,
        entity_name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._api_client = coordinator.api
        self._attr_unique_id = f"{entry.data[CONF_NAME]}.{entity_name}"
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer=MANUFACTURER,
            sw_version=coordinator.data.state.firmware_version
            if coordinator.data.state
            else "",
        )
        self._api_client = entry.runtime_data.client


@dataclass
class WatergateData:
    """Data for the A. O. Smith integration."""

    client: WatergateLocalApiClient
    coordinator: WatergateDataCoordinator
    sonic_name: str
