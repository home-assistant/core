"""Support for switches on Frontier Silicon Devices (Medion, Hama, Auna,...)."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import partial
import logging
from typing import Any

from afsapi import AFSAPI

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FrontierSiliconConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AFSAPISwitchEntityDescription(SwitchEntityDescription):
    """Describes Frontier Silicon switch entity."""

    is_on_fn: Callable[[AFSAPI], Callable[[], Coroutine[Any, Any, bool]]]
    turn_on_fn: Callable[[AFSAPI], Callable[[], Coroutine[Any, Any, None]]]
    turn_off_fn: Callable[[AFSAPI], Callable[[], Coroutine[Any, Any, None]]]


SWITCHES: tuple[AFSAPISwitchEntityDescription, ...] = (
    AFSAPISwitchEntityDescription(
        key="dst",
        translation_key="dst",
        is_on_fn=lambda afsapi: afsapi.get_dst,
        turn_on_fn=lambda afsapi: partial(afsapi.set_dst, True),
        turn_off_fn=lambda afsapi: partial(afsapi.set_dst, False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FrontierSiliconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Frontier Silicon entity."""

    afsapi = config_entry.runtime_data
    async_add_entities(
        [
            AFSAPISwitch(config_entry.entry_id, config_entry.title, afsapi, description)
            for description in SWITCHES
        ],
        True,
    )


class AFSAPISwitch(SwitchEntity):
    """Representation of a switch on a Frontier Silicon device."""

    entity_description: AFSAPISwitchEntityDescription
    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        unique_id: str,
        name: str | None,
        afsapi: AFSAPI,
        description: AFSAPISwitchEntityDescription,
    ) -> None:
        """Initialize the Frontier Silicon API device."""
        self.fs_device = afsapi
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )
        self._attr_unique_id = f"{unique_id}_{description.key}"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.turn_off_fn(self.fs_device)()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.turn_on_fn(self.fs_device)()

    async def async_update(self) -> None:
        """Update AdGuard Home entity."""

        if not self.enabled:
            return

        # try:
        await self._update()
        self._attr_available = True
        # except AdGuardHomeError:
        #    if self._attr_available:
        #        LOGGER.debug(
        #            "An error occurred while updating AdGuard Home sensor",
        #            exc_info=True,
        #        )
        #    self._attr_available = False

    async def _update(self) -> None:
        """Update AdGuard Home entity."""
        self._attr_is_on = await self.entity_description.is_on_fn(self.fs_device)()
