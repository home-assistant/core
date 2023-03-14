"""Service platform helper."""
from __future__ import annotations

import logging
from typing import Generic, TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_prepare_setup_platform

from .engine import Engine
from .engine_platform import EnginePlatform
from .typing import ConfigType

_EngineT = TypeVar("_EngineT", bound=Engine)


class EngineComponent(Generic[_EngineT]):
    """Track engines for a component."""

    def __init__(
        self,
        logger: logging.Logger,
        domain: str,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> None:
        """Initialize the engine component."""
        self.logger = logger
        self.domain = domain
        self.hass = hass
        self.config = config
        self._platforms: dict[str, EnginePlatform[_EngineT]] = {}

    @callback
    def async_get_engine(self, config_entry_id: str) -> _EngineT | None:
        """Return a wrapped engine."""
        platform = self._platforms.get(config_entry_id)
        return None if platform is None else platform.engine

    @callback
    def async_get_engines(self) -> list[_EngineT]:
        """Return a wrapped engine."""
        return [
            platform.engine
            for platform in self._platforms.values()
            if platform.engine is not None
        ]

    async def async_setup_entry(self, config_entry: ConfigEntry) -> bool:
        """Set up a config entry."""
        platform_type = config_entry.domain
        platform = await async_prepare_setup_platform(
            self.hass,
            # In future PR we should make hass_config part of the constructor
            # params.
            self.config or {},
            self.domain,
            platform_type,
        )

        if platform is None:
            return False

        key = config_entry.entry_id

        if key in self._platforms:
            raise ValueError("Config entry has already been setup!")

        self._platforms[key] = EnginePlatform(
            self.logger,
            self.hass,
            config_entry,
            platform,
        )

        return await self._platforms[key].async_setup_entry()

    async def async_unload_entry(self, config_entry: ConfigEntry) -> bool:
        """Unload a config entry."""
        key = config_entry.entry_id

        if (platform := self._platforms.pop(key, None)) is None:
            raise ValueError("Config entry was never loaded!")

        return await platform.async_unload_entry()
