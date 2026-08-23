"""Platform for OpenGarage opener lights."""

from typing import Any, cast, override

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenGarageConfigEntry, OpenGarageDataUpdateCoordinator
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

    async_add_entities(
        [
            OpenGarageLight(
                coordinator,
                cast(str, entry.unique_id),
                LIGHT_DESCRIPTION,
            )
        ]
    )


class OpenGarageLight(OpenGarageEntity, LightEntity):
    """Representation of an OpenGarage-controlled opener light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self,
        coordinator: OpenGarageDataUpdateCoordinator,
        device_id: str,
        description: LightEntityDescription,
    ) -> None:
        """Initialize the light."""
        self._attr_is_on = False
        super().__init__(coordinator, device_id, description)

    @callback
    @override
    def _update_attr(self) -> None:
        """Update the light state from the coordinator."""
        self._attr_is_on = bool(self.coordinator.data[LIGHT_DESCRIPTION.key])

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the opener light."""
        await self._async_set_light(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the opener light."""
        await self._async_set_light(False)

    async def _async_set_light(self, turn_on: bool) -> None:
        """Set and optimistically update the opener light state."""
        result = await self.coordinator.open_garage_connection.set_light(turn_on)
        if result == 1:
            self.coordinator.async_set_updated_data(
                {**self.coordinator.data, LIGHT_DESCRIPTION.key: int(turn_on)}
            )
            return

        if result == 2:
            raise HomeAssistantError(
                translation_domain="opengarage",
                translation_key="light_control_invalid_auth",
            )

        if result is None:
            raise HomeAssistantError(
                translation_domain="opengarage",
                translation_key="light_control_unavailable",
            )

        raise HomeAssistantError(
            translation_domain="opengarage",
            translation_key="light_control_failed",
            translation_placeholders={"result": str(result)},
        )
