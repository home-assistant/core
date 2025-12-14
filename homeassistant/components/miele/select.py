"""Platform for Miele select entity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
import logging
from typing import Final

from aiohttp import ClientResponseError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, MieleAppliance
from .coordinator import MieleConfigEntry
from .entity import MieleDevice, MieleEntity

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


class MieleModes(IntEnum):
    """Modes for fridge/freezer."""

    NORMAL = 0
    SABBATH = 1
    PARTY = 2
    HOLIDAY = 3


@dataclass(frozen=True, kw_only=True)
class MieleSelectDescription(SelectEntityDescription):
    """Class describing Miele select entities."""

    value_fn: Callable[[MieleDevice], StateType]


@dataclass
class MieleSelectDefinition:
    """Class for defining select entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleSelectDescription


SELECT_TYPES: Final[tuple[MieleSelectDefinition, ...]] = (
    MieleSelectDefinition(
        types=(
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE,
            MieleAppliance.FRIDGE_FREEZER,
        ),
        description=MieleSelectDescription(
            key="fridge_freezer_modes",
            value_fn=lambda value: 1,
            translation_key="fridge_freezer_mode",
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator = config_entry.runtime_data
    added_devices: set[str] = set()

    def _async_add_new_devices() -> None:
        nonlocal added_devices
        new_devices_set, current_devices = coordinator.async_add_devices(added_devices)
        added_devices = current_devices

        async_add_entities(
            MieleSelectMode(coordinator, device_id, definition.description)
            for device_id, device in coordinator.data.devices.items()
            for definition in SELECT_TYPES
            if device_id in new_devices_set and device.device_type in definition.types
        )

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))
    _async_add_new_devices()


class MieleSelectMode(MieleEntity, SelectEntity):
    """Representation of a Select mode entity."""

    entity_description: MieleSelectDescription

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        return sorted(
            {MieleModes(x).name.lower() for x in self.action.modes}
            | {self.current_option}
        )

    @property
    def current_option(self) -> str:
        """Retrieve currently selected option."""
        # There is no direct mapping from Miele 3rd party API, so we infer the
        # current mode based on available modes in action.modes

        action_modes = set(self.action.modes)
        if action_modes in ({1}, {1, 2}, {1, 3}, {1, 2, 3}):
            return MieleModes.NORMAL.name.lower()

        if action_modes in ({0}, {0, 2}, {0, 3}, {0, 2, 3}):
            return MieleModes.SABBATH.name.lower()

        if action_modes in ({0, 1}, {0, 1, 3}):
            return MieleModes.PARTY.name.lower()

        if action_modes == {0, 1, 2}:
            return MieleModes.HOLIDAY.name.lower()

        return MieleModes.NORMAL.name.lower()

    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        new_mode = MieleModes[option.upper()].value
        if new_mode not in self.action.modes:
            _LOGGER.debug("Option '%s' is not available for %s", option, self.entity_id)
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={
                    "option": option,
                    "entity": self.entity_id,
                },
            )
        try:
            await self.api.send_action(
                self._device_id,
                {"modes": new_mode},
            )
        except ClientResponseError as err:
            _LOGGER.debug("Error setting select state for %s: %s", self.entity_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from err

        # Refresh data as API does not push changes for modes updates
        await self.coordinator.async_request_refresh()
