"""Support for SLZB-06 buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from pysmlight.web import CmdWrapper

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SmConfigEntry, SmDataUpdateCoordinator
from .entity import SmEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SmButtonDescription(ButtonEntityDescription):
    """Class to describe a Button entity."""

    press_fn: Callable[[CmdWrapper, int], Awaitable[None]]


BUTTONS: list[SmButtonDescription] = [
    SmButtonDescription(
        key="core_restart",
        translation_key="core_restart",
        device_class=ButtonDeviceClass.RESTART,
        press_fn=lambda cmd, idx: cmd.reboot(),
    ),
    SmButtonDescription(
        key="zigbee_restart",
        translation_key="zigbee_restart",
        device_class=ButtonDeviceClass.RESTART,
        press_fn=lambda cmd, idx: cmd.zb_restart(),
    ),
    SmButtonDescription(
        key="zigbee_flash_mode",
        translation_key="zigbee_flash_mode",
        entity_registry_enabled_default=False,
        press_fn=lambda cmd, idx: cmd.zb_bootloader(),
    ),
]

ROUTER = SmButtonDescription(
    key="reconnect_zigbee_router",
    translation_key="reconnect_zigbee_router",
    entity_registry_enabled_default=False,
    press_fn=lambda cmd, idx: cmd.zb_router(idx=idx),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SMLIGHT buttons based on a config entry."""
    coordinator = entry.runtime_data.data
    radios = coordinator.data.info.radios
    assert radios is not None

    async_add_entities(SmButton(coordinator, button) for button in BUTTONS)
    entity_created = [False, False]

    @callback
    def _check_router(startup: bool = False) -> None:
        def router_entity(router: SmButtonDescription, idx: int) -> None:
            nonlocal entity_created
            zb_type = coordinator.data.info.radios[idx].zb_type

            if zb_type == 1 and not entity_created[idx]:
                async_add_entities([SmButton(coordinator, router, idx)])
                entity_created[idx] = True
            elif zb_type != 1 and (startup or entity_created[idx]):
                entity_registry = er.async_get(hass)
                button = f"_{idx}" if idx else ""
                if entity_id := entity_registry.async_get_entity_id(
                    BUTTON_DOMAIN,
                    DOMAIN,
                    f"{coordinator.unique_id}-{router.key}{button}",
                ):
                    entity_registry.async_remove(entity_id)

        for idx, _ in enumerate(radios):
            router_entity(ROUTER, idx)

    coordinator.async_add_listener(_check_router)
    _check_router(startup=True)


class SmButton(SmEntity, ButtonEntity):
    """Defines a SLZB-06 button."""

    coordinator: SmDataUpdateCoordinator
    entity_description: SmButtonDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmButtonDescription,
        idx: int = 0,
    ) -> None:
        """Initialize SLZB-06 button entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self.idx = idx
        button = f"_{idx}" if idx else ""
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}{button}"

    async def async_press(self) -> None:
        """Trigger button press."""
        await self.entity_description.press_fn(self.coordinator.client.cmds, self.idx)
