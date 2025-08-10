"""Support for Magic home button."""

from __future__ import annotations

from flux_led.aio import AIOWifiLedBulb
from flux_led.protocol import RemoteConfig

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FluxLedConfigEntry
from .entity import FluxBaseEntity

_RESTART_KEY = "restart"
_UNPAIR_REMOTES_KEY = "unpair_remotes"

RESTART_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key=_RESTART_KEY,
    device_class=ButtonDeviceClass.RESTART,
)
UNPAIR_REMOTES_DESCRIPTION = ButtonEntityDescription(
    key=_UNPAIR_REMOTES_KEY,
    translation_key="unpair_remotes",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FluxLedConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Magic Home button based on a config entry."""
    coordinator = entry.runtime_data
    device = coordinator.device
    entities: list[FluxButton] = [
        FluxButton(coordinator.device, entry, RESTART_BUTTON_DESCRIPTION)
    ]
    if device.paired_remotes is not None:
        entities.append(
            FluxButton(coordinator.device, entry, UNPAIR_REMOTES_DESCRIPTION)
        )

    async_add_entities(entities)


class FluxButton(FluxBaseEntity, ButtonEntity):
    """Representation of a Flux button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: FluxLedConfigEntry,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        self.entity_description = description
        super().__init__(device, entry)
        base_unique_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_unique_id}_{description.key}"

    async def async_press(self) -> None:
        """Send out a command."""
        if self.entity_description.key == _RESTART_KEY:
            await self._device.async_reboot()
        else:
            await self._device.async_unpair_remotes()
            await self._device.async_config_remotes(RemoteConfig.OPEN)
