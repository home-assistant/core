"""Platform for Miele button integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

import aiohttp

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PROCESS_ACTION, MieleActions, MieleAppliance
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleButtonDescription(ButtonEntityDescription):
    """Class describing Miele button entities."""

    press_data: dict[str, MieleActions]


@dataclass
class MieleButtonDefinition:
    """Class for defining button entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleButtonDescription


BUTTON_TYPES: Final[tuple[MieleButtonDefinition, ...]] = (
    MieleButtonDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.STEAM_OVEN_MK2,
            MieleAppliance.DIALOG_OVEN,
        ),
        description=MieleButtonDescription(
            key="start",
            translation_key="start",
            press_data={PROCESS_ACTION: MieleActions.START},
        ),
    ),
    MieleButtonDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.HOOD,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.STEAM_OVEN_MK2,
            MieleAppliance.DIALOG_OVEN,
        ),
        description=MieleButtonDescription(
            key="stop",
            translation_key="stop",
            press_data={PROCESS_ACTION: MieleActions.STOP},
        ),
    ),
    MieleButtonDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.WASHER_DRYER,
        ),
        description=MieleButtonDescription(
            key="pause",
            translation_key="pause",
            press_data={PROCESS_ACTION: MieleActions.PAUSE},
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MieleButton(coordinator, device_id, definition.description)
        for device_id, device in coordinator.data.devices.items()
        for definition in BUTTON_TYPES
        if device.device_type in definition.types
    )


class MieleButton(MieleEntity, ButtonEntity):
    """Representation of a Button."""

    entity_description: MieleButtonDescription

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: MieleButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id, description)
        self.api = coordinator.api

    def _action_available(self, action: MieleActions) -> bool:
        """Check if action is available according to API."""
        if PROCESS_ACTION in action:
            return (
                action[PROCESS_ACTION] in self.coordinator.data.actions.process_actions
            )
        _LOGGER.debug("Action not found: %s", action)
        return False

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""

        return super().available and self._action_available(
            self.entity_description.press_data
        )

    async def async_press(self) -> None:
        """Press the button."""
        _LOGGER.debug("Press: %s", self.entity_description.key)
        if self._action_available(self.entity_description.press_data):
            try:
                await self.api.send_action(
                    self.device_id, self.entity_description.press_data
                )
            except aiohttp.ClientResponseError as ex:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="set_state_error",
                    translation_placeholders={
                        "entity": self.entity_id,
                    },
                ) from ex
