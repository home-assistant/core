"""Platform for Miele light entity."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Final

import aiohttp

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AMBIENT_LIGHT, DOMAIN, LIGHT, LIGHT_OFF, LIGHT_ON, MieleAppliance
from .coordinator import MieleConfigEntry
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleLightDescription(LightEntityDescription):
    """Class describing Miele light entities."""

    data_tag: str
    preset_modes: list | None = None
    supported_features = LightEntityFeature(0)


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
            data_tag="light",
            # translation_key="light",
        ),
    ),
    MieleLightDefinition(
        types=(MieleAppliance.HOOD,),
        description=MieleLightDescription(
            key="ambient_light",
            data_tag="ambientlight",
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

    entities = [
        MieleLight(coordinator, device_id, definition.description)
        for device_id, device in coordinator.data.devices.items()
        for definition in LIGHT_TYPES
        if device.device_type in definition.types
    ]

    async_add_entities(entities)


class MieleLight(MieleEntity, LightEntity):
    """Representation of a Light."""

    entity_description: MieleLightDescription
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    # def __init__(
    #     self,
    #     coordinator: MieleDataUpdateCoordinator,
    #     device_id: str,
    #     description: MieleLightDescription,
    # ) -> None:
    #     """Initialize the light."""
    #     super().__init__(coordinator, device_id, description)
    #     self.api = coordinator.api

    #     self._attr_supported_features = self.entity_description.supported_features

    @property
    def is_on(self) -> bool | None:
        """Return current on/off state."""
        return (
            getattr(
                self.device,
                self.entity_description.data_tag,
                None,
            )
            == LIGHT_ON
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._async_turn_light(LIGHT_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_turn_light(LIGHT_OFF)

    async def _async_turn_light(self, mode: int) -> None:
        """Set light to mode."""
        light_type = (
            AMBIENT_LIGHT if self.entity_description.key == "ambient_light" else LIGHT
        )
        try:
            await self.api.send_action(self._device_id, {light_type: mode})
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from err
