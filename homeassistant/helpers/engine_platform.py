"""Service platform helper."""
import logging
from typing import Generic, Protocol, TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .engine import Engine

_EngineT_co = TypeVar("_EngineT_co", bound=Engine, covariant=True)


class EnginePlatformModule(Protocol[_EngineT_co]):
    """Protocol type for engine platform modules."""

    async def async_setup_entry(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> _EngineT_co:
        """Set up an integration platform from a config entry."""


class EnginePlatform(Generic[_EngineT_co]):
    """Track engines for a platform."""

    def __init__(
        self,
        logger: logging.Logger,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        platform: EnginePlatformModule,
    ) -> None:
        """Initialize the engine platform."""
        self.logger = logger
        self.hass = hass
        self.config_entry = config_entry
        self.platform = platform
        self.engine: _EngineT_co | None = None

    async def async_setup_entry(self) -> bool:
        """Set up a config entry."""
        try:
            engine = await self.platform.async_setup_entry(self.hass, self.config_entry)
        except Exception:  # pylint: disable=broad-except
            self.logger.exception(
                "Error setting up entry %s", self.config_entry.entry_id
            )
            return False

        await engine.async_internal_added_to_hass()
        await engine.async_added_to_hass()

        self.engine = engine
        return True

    async def async_unload_entry(self) -> bool:
        """Unload a config entry."""
        if self.engine is None:
            return True

        await self.engine.async_internal_will_remove_from_hass()
        await self.engine.async_will_remove_from_hass()
        self.engine = None
        return True
