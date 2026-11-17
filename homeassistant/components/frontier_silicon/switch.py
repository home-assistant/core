"""Support for switches on Frontier Silicon Devices (Medion, Hama, Auna,...)."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import partial
import logging
from typing import Any, override

from afsapi import AFSAPI, FSConnectionError, FSNotImplementedError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FrontierSiliconConfigEntry
from .entity import FrontierSiliconEntity, fs_command_exception_wrap

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
        entity_category=EntityCategory.CONFIG,
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

    # only add switch entities for nodes which exist on the target device
    available_switches = []
    max_tries_per_entity = 3
    for description in SWITCHES:
        connection_attempt_succeeded = False
        num_tries = 0
        while num_tries < max_tries_per_entity:
            num_tries += 1
            try:
                _ = await description.is_on_fn(afsapi)()
            except FSNotImplementedError:
                # we connected OK, but the switch is not supported, so stop trying
                connection_attempt_succeeded = True
                break
            except FSConnectionError:
                # retry in case the connection error is transient
                continue
            available_switches.append(description)
            connection_attempt_succeeded = True
            break
        if not connection_attempt_succeeded:
            _LOGGER.warning("Could not connect to Frontier Silicon device during setup")

    async_add_entities(
        [
            AFSAPISwitch(config_entry, afsapi, description)
            for description in available_switches
        ],
        True,
    )


class AFSAPISwitch(FrontierSiliconEntity, SwitchEntity):
    """Representation of a switch on a Frontier Silicon device."""

    entity_description: AFSAPISwitchEntityDescription

    def __init__(
        self,
        config_entry: FrontierSiliconConfigEntry,
        afsapi: AFSAPI,
        description: AFSAPISwitchEntityDescription,
    ) -> None:
        """Initialize the Frontier Silicon API device."""
        super().__init__(afsapi, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}-{description.key}"

    @fs_command_exception_wrap
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.turn_off_fn(self.fs_device)()

    @fs_command_exception_wrap
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.turn_on_fn(self.fs_device)()

    @override
    async def _fs_update(self) -> None:
        """Update Frontier Silicon entity."""
        self._attr_is_on = await self.entity_description.is_on_fn(self.fs_device)()
