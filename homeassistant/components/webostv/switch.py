"""Support for LG webOS TV switch."""

from typing import Any, override

from aiowebostv import WebOsTvServiceNotFoundError

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import WebOsTvConfigEntry
from .entity import WebOsTvEntity, cmd

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG webOS TV switch platform."""
    async_add_entities([LgWebOSScreenSwitchEntity(entry)])


class LgWebOSScreenSwitchEntity(WebOsTvEntity, SwitchEntity):
    """Representation of a LG webOS TV Screen Switch."""

    _attr_translation_key = "screen"
    _attr_entity_registry_enabled_default = False

    def __init__(self, entry: WebOsTvConfigEntry) -> None:
        """Initialize the screen switch entity."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.unique_id}_screen"
        self._unsupported = False

    @property
    @override
    def available(self) -> bool:
        """Return true if the entity is available."""
        return (
            super().available and self._client.tv_state.is_on and not self._unsupported
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if screen is on."""
        return self._client.tv_state.is_screen_on

    @cmd
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the screen on."""
        await self._async_set_screen_state(True)

    @cmd
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the screen off."""
        await self._async_set_screen_state(False)

    async def _async_set_screen_state(self, state: bool) -> None:
        """Set the screen state, marking the switch unsupported on a 404."""
        try:
            await self._client.set_screen_state(state)
        except WebOsTvServiceNotFoundError as error:
            self._unsupported = True
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="screen_control_not_supported",
                translation_placeholders={"name": self.coordinator.name},
            ) from error
