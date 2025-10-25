"""Platform for Miele light entity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final

import aiohttp

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import AMBIENT_LIGHT, DOMAIN, LIGHT, LIGHT_OFF, LIGHT_ON, MieleAppliance
from .coordinator import MieleConfigEntry
from .entity import MieleDevice, MieleEntity

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleLightDescription(LightEntityDescription):
    """Class describing Miele light entities."""

    value_fn: Callable[[MieleDevice], StateType]
    light_type: str


@dataclass
class MieleLightDefinition:
    """Class for defining light entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleLightDescription


LIGHT_TYPES: Final[tuple[MieleLightDefinition, ...]] = (
    MieleLightDefinition(
        types=(
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.HOOD,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleLightDescription(
            key="light",
            value_fn=lambda value: value.state_light,
            light_type=LIGHT,
            translation_key="light",
        ),
    ),
    MieleLightDefinition(
        types=(MieleAppliance.HOOD,),
        description=MieleLightDescription(
            key="ambient_light",
            value_fn=lambda value: value.state_ambient_light,
            light_type=AMBIENT_LIGHT,
            translation_key="ambient_light",
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light platform."""
    coordinator = config_entry.runtime_data
    added_devices: set[str] = set()

    def _async_add_new_devices() -> None:
        nonlocal added_devices
        new_devices_set, current_devices = coordinator.async_add_devices(added_devices)
        added_devices = current_devices

        async_add_entities(
            MieleLight(coordinator, device_id, definition.description)
            for device_id, device in coordinator.data.devices.items()
            for definition in LIGHT_TYPES
            if device_id in new_devices_set and device.device_type in definition.types
        )

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))
    _async_add_new_devices()


class MieleLight(MieleEntity, LightEntity):
    """Representation of a Light."""

    entity_description: MieleLightDescription
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool:
        """Return current on/off state."""
        return self.entity_description.value_fn(self.device) == LIGHT_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self.async_turn_light(LIGHT_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.async_turn_light(LIGHT_OFF)

    async def async_turn_light(self, mode: int) -> None:
        """Set light to mode."""
        try:
            await self.api.send_action(
                self._device_id, {self.entity_description.light_type: mode}
            )
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from err
