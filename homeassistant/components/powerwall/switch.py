"""Support for Powerwall Switches (V2 API only)."""

from typing import Any

from tesla_powerwall import GridStatus, IslandMode

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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

    _attr_name = "Powerwall Off-Grid"
    _attr_unique_id = "powerwall_off_grid"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool:
        """Return true if the powerwall is off-grid."""
        return self.coordinator.data.grid_status in OFF_GRID_STATUSES

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn off-grid mode on."""
        await self.hass.async_add_executor_job(
            self.power_wall.set_island_mode, IslandMode.OFFGRID
        )
        self._attr_is_on = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off-grid mode off (return to on-grid usage)."""
        await self.hass.async_add_executor_job(
            self.power_wall.set_island_mode, IslandMode.ONGRID
        )
        self._attr_is_on = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
