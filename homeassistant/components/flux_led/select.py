"""Support for Magic Home select."""
from __future__ import annotations

from flux_led.aio import AIOWifiLedBulb
from flux_led.protocol import PowerRestoreState

from homeassistant import config_entries
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FluxLedUpdateCoordinator
from .const import DOMAIN
from .entity import FluxBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux switches."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FluxPowerState(coordinator.device, entry)])


class FluxPowerState(FluxBaseEntity, SelectEntity):
    """Representation of a Flux power restore state option."""

    _attr_should_poll = False

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize the select."""
        super().__init__(device, entry)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_name = f"{entry.data[CONF_NAME]} Power Restored"
        if entry.unique_id:
            self._attr_unique_id = f"{entry.unique_id}_power_restored"
        self._attr_options = [option.name for option in PowerRestoreState]
        self._name_to_state = {option.name: option for option in PowerRestoreState}
        self._async_set_current_option_from_device()

    @callback
    def _async_set_current_option_from_device(self) -> None:
        restore_states = self._device.power_restore_states
        assert restore_states is not None
        self._attr_current_option = restore_states.channel1.name

    async def async_select_option(self, option: str) -> None:
        """Change the Select Entity Option."""
        await self._device.async_set_power_restore(channel1=self._name_to_state[option])
        self._async_set_current_option_from_device()
        self.async_write_ha_state()
