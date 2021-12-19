"""Support for Magic home button."""
from __future__ import annotations

from flux_led.aio import AIOWifiLedBulb

from homeassistant import config_entries
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
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
    """Set up Magic Home button based on a config entry."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FluxRestartButton(coordinator.device, entry)])


class FluxRestartButton(FluxBaseEntity, ButtonEntity):
    """Representation of a Flux restart button."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize the reboot button."""
        super().__init__(device, entry)
        self._attr_name = f"{entry.data[CONF_NAME]} Restart"
        if entry.unique_id:
            self._attr_unique_id = f"{entry.unique_id}_restart"

    async def async_press(self) -> None:
        """Send out a restart command."""
        await self._device.async_reboot()
