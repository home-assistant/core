"""Support for Palazzetti lights."""

from typing import Any, override

from pypalazzetti.exceptions import CommunicationError

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import PalazzettiConfigEntry, PalazzettiDataUpdateCoordinator
from .entity import PalazzettiEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PalazzettiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Palazzetti light platform."""

    coordinator = config_entry.runtime_data
    if coordinator.client.has_light_control:
        async_add_entities([PalazzettiLightEntity(coordinator)])


class PalazzettiLightEntity(PalazzettiEntity, LightEntity):
    """Representation of a Palazzetti light."""

    _attr_translation_key = "light"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self,
        coordinator: PalazzettiDataUpdateCoordinator,
    ) -> None:
        """Initialize a Palazzetti light."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.unique_id

    @property
    @override
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.coordinator.client.is_light_on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        try:
            if not await self.coordinator.client.set_light(True):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="cannot_connect"
                )
        except CommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err

        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        try:
            if not await self.coordinator.client.set_light(False):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="cannot_connect"
                )
        except CommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err

        await self.coordinator.async_request_refresh()
