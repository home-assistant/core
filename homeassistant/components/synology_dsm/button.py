"""Support for Synology DSM buttons."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SynoApi
from .const import DOMAIN
from .coordinator import SynologyDSMConfigEntry

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SynologyDSMbuttonDescription(ButtonEntityDescription):
    """Class to describe a Synology DSM button entity."""

    press_action: Callable[[SynoApi], Callable[[], Coroutine[Any, Any, None]]]


BUTTONS: Final = [
    SynologyDSMbuttonDescription(
        key="reboot",
        name="Reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda syno_api: syno_api.async_reboot,
    ),
    SynologyDSMbuttonDescription(
        key="shutdown",
        name="Shutdown",
        icon="mdi:power",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda syno_api: syno_api.async_shutdown,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SynologyDSMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set buttons for device."""
    data = entry.runtime_data
    async_add_entities(SynologyDSMButton(data.api, button) for button in BUTTONS)


class SynologyDSMButton(ButtonEntity):
    """Defines a Synology DSM button."""

    entity_description: SynologyDSMbuttonDescription

    def __init__(
        self,
        api: SynoApi,
        description: SynologyDSMbuttonDescription,
    ) -> None:
        """Initialize the Synology DSM binary_sensor entity."""
        self.entity_description = description
        self.syno_api = api
        assert api.network is not None
        assert api.information is not None
        self._attr_name = f"{api.network.hostname} {description.name}"
        self._attr_unique_id = f"{api.information.serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api.information.serial)}
        )

    async def async_press(self) -> None:
        """Triggers the Synology DSM button press service."""
        assert self.syno_api.network is not None
        LOGGER.debug(
            "Trigger %s for %s",
            self.entity_description.key,
            self.syno_api.network.hostname,
        )
        await self.entity_description.press_action(self.syno_api)()
