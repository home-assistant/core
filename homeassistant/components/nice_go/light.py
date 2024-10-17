"""Nice G.O. light."""

from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from nice_go import ApiError

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NiceGOConfigEntry
from .const import DOMAIN
from .entity import NiceGOEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NiceGOConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nice G.O. light."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        NiceGOLightEntity(coordinator, device_id, device_data.name)
        for device_id, device_data in coordinator.data.items()
        if device_data.light_status is not None
    )


class NiceGOLightEntity(NiceGOEntity, LightEntity):
    """Light for Nice G.O. devices."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "light"

    @property
    def is_on(self) -> bool:
        """Return if the light is on or not."""
        if TYPE_CHECKING:
            assert self.data.light_status is not None
        return self.data.light_status

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""

        try:
            await self.coordinator.api.light_on(self._device_id)
        except (ApiError, ClientError) as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="light_on_error",
                translation_placeholders={"exception": str(error)},
            ) from error

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        try:
            await self.coordinator.api.light_off(self._device_id)
        except (ApiError, ClientError) as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="light_off_error",
                translation_placeholders={"exception": str(error)},
            ) from error
