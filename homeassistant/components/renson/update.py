"""Platform to control a Renson ventilation unit."""
from __future__ import annotations

# from renson_endura_delta.field_enum import CURRENT_LEVEL_FIELD, DataType
from renson_endura_delta.renson import RensonVentilation
from renson_endura_delta.field_enum import FIRMWARE_VERSION_FIELD

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RensonFirmwareCoordinator
from .const import DOMAIN
from .entity import RensonEntity


class RensonUpdate(RensonEntity, UpdateEntity):
    """Representation of the Renson firmware update check."""

    def __init__(
        self, api: RensonVentilation, coordinator: RensonFirmwareCoordinator
    ) -> None:
        """Initialize the Renson firmware update check."""
        super().__init__("update", api, coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_installed_version = self.api.get_field_value(
            self.coordinator.data, FIRMWARE_VERSION_FIELD.name
        ).split()[-1]

        self._attr_latest_version = self.coordinator.data["latest_firmware_version"]

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson update platform."""
    api: RensonVentilation = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator: RensonFirmwareCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "fw_coordinator"
    ]

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([RensonUpdate(api, coordinator)])

    await coordinator.async_config_entry_first_refresh()
