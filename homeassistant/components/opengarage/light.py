"""Platform for OpenGarage opener lights."""

from typing import TYPE_CHECKING, Any, override

from aiohttp import ClientError
from opengarage.errors import OpenGarageError

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import OpenGarageConfigEntry
from .entity import OpenGarageEntity

LIGHT_DESCRIPTION = LightEntityDescription(key="light", translation_key="light")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenGarageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an opener light when the firmware reports light state."""
    coordinator = entry.runtime_data
    if LIGHT_DESCRIPTION.key not in coordinator.data:
        return
    if TYPE_CHECKING:
        assert entry.unique_id is not None

    async_add_entities(
        [
            OpenGarageLight(
                coordinator,
                entry.unique_id,
                LIGHT_DESCRIPTION,
            )
        ]
    )


class OpenGarageLight(OpenGarageEntity, LightEntity):
    """Representation of an OpenGarage-controlled opener light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the opener light is on."""
        state = self.coordinator.data.get(LIGHT_DESCRIPTION.key)
        return state == 1 if state in (0, 1) else None

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the opener light."""
        await self._async_set_light(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the opener light."""
        await self._async_set_light(False)

    async def _async_set_light(self, turn_on: bool) -> None:
        """Set the opener light and request fresh device state."""
        try:
            result = await self.coordinator.open_garage_connection.set_light(turn_on)
        except (ClientError, TimeoutError, OpenGarageError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="light_control_unavailable",
            ) from err
        if result == 1:
            await self.coordinator.async_refresh()
            return

        if result == 2:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="light_control_invalid_auth",
            )

        if result is None:
            await self.coordinator.async_refresh()
            if self.coordinator.last_update_success and self.is_on is turn_on:
                return
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="light_control_state_not_confirmed",
            )

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="light_control_failed",
            translation_placeholders={"result": str(result)},
        )
