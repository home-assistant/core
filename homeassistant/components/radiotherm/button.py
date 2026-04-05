"""Support for Radio Thermostat buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RadioThermUpdateCoordinator
from .entity import RadioThermostatEntity
from .util import async_set_time

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons for a radiotherm device."""
    coordinator: RadioThermUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RadioThermSyncTimeButton(coordinator, entry),
            RadioThermCheckCloudButton(coordinator, entry),
        ]
    )


class RadioThermSyncTimeButton(RadioThermostatEntity, ButtonEntity):
    """Provides radiotherm sync time button support."""

    _attr_translation_key = "sync_time"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: RadioThermUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the set time button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.init_data.mac}_sync_time"

    def _process_data(self) -> None:
        """No state to process for a button."""

    async def async_press(self) -> None:
        """Set the time on the thermostat."""
        time_coro = async_set_time(self.hass, self.coordinator.init_data.tstat)
        await time_coro


class RadioThermCheckCloudButton(RadioThermostatEntity, ButtonEntity):
    """Provides a button to check cloud enabled status."""

    _attr_translation_key = "check_cloud"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: RadioThermUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the check cloud button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.init_data.mac}_check_cloud"

    def _process_data(self) -> None:
        """No state to process for a button."""

    def _get_cloud(self) -> dict:
        """GET /cloud from the thermostat."""
        return self.device.cloud["raw"]

    async def async_press(self) -> None:
        """Check cloud enabled status from the thermostat."""
        result = await self.hass.async_add_executor_job(self._get_cloud)
        self.coordinator.cloud_enabled = bool(result.get("enabled", 0))
        self.coordinator.async_update_listeners()
