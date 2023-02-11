"""Support for Powerwall Switches (V2 API only)."""

from typing import Any

from tesla_powerwall import GridStatus, IslandMode, PowerwallError

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PowerWallEntity
from .models import PowerwallRuntimeData

OFF_GRID_STATUSES = {
    GridStatus.TRANSITION_TO_ISLAND,
    GridStatus.ISLANDED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powerwall switch platform from Powerwall resources."""
    powerwall_data: PowerwallRuntimeData = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([PowerwallOffGridEnabledEntity(powerwall_data)])


class PowerwallOffGridEnabledEntity(PowerWallEntity, SwitchEntity):
    """Representation of a Switch entity for Powerwall Off-grid operation."""

    _attr_name = "Off-Grid operation"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, powerwall_data: PowerwallRuntimeData) -> None:
        """Initialize powerwall entity and unique id."""
        super().__init__(powerwall_data)
        self._attr_unique_id = f"{self.base_unique_id}_off_grid_operation"

    @property
    def is_on(self) -> bool:
        """Return true if the powerwall is off-grid."""
        return self.coordinator.data.grid_status in OFF_GRID_STATUSES

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn off-grid mode on."""
        await self._async_set_island_mode(IslandMode.OFFGRID)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off-grid mode off (return to on-grid usage)."""
        await self._async_set_island_mode(IslandMode.ONGRID)

    async def _async_set_island_mode(self, island_mode: IslandMode) -> None:
        """Toggles off-grid mode using the island_mode argument."""
        try:
            await self.hass.async_add_executor_job(
                self.power_wall.set_island_mode, island_mode
            )
        except PowerwallError as ex:
            raise HomeAssistantError(
                f"Setting off-grid operation to {island_mode} failed: {ex}"
            ) from ex

        self._attr_is_on = island_mode == IslandMode.OFFGRID
        self.async_write_ha_state()

        await self.coordinator.async_request_refresh()
