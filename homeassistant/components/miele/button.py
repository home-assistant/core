"""Platform for Miele button integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

import aiohttp
from pymiele import MieleDevice

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PROCESS_ACTION, MieleActions, MieleAppliance
from .coordinator import MieleConfigEntry
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleButtonDescription(ButtonEntityDescription):
    """Class describing Miele button entities."""

    press_data: MieleActions


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
            press_data=MieleActions.START,
            entity_registry_enabled_default=False,
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
            press_data=MieleActions.STOP,
            entity_registry_enabled_default=False,
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
            press_data=MieleActions.PAUSE,
            entity_registry_enabled_default=False,
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

    def _async_add_new_devices(new_devices: dict[str, MieleDevice]) -> None:
        async_add_entities(
            MieleButton(coordinator, device_id, definition.description)
            for device_id, device in new_devices.items()
            for definition in BUTTON_TYPES
            if device.device_type in definition.types
        )

    coordinator.new_device_callbacks.append(_async_add_new_devices)
    _async_add_new_devices(coordinator.data.devices)


class MieleButton(MieleEntity, ButtonEntity):
    """Representation of a Button."""

    entity_description: MieleButtonDescription

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""

        return (
            super().available
            and self.entity_description.press_data in self.action.process_actions
        )

    async def async_press(self) -> None:
        """Press the button."""
        _LOGGER.debug("Press: %s", self.entity_description.key)
        try:
            await self.api.send_action(
                self._device_id,
                {PROCESS_ACTION: self.entity_description.press_data},
            )
        except aiohttp.ClientResponseError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from ex
