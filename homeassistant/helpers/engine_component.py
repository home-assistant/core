"""Engine component helper."""
from __future__ import annotations

import logging
from typing import Generic, Protocol, TypeVar, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_prepare_setup_platform

from .typing import ConfigType


class Engine:
    """Base class for Home Assistant engines."""

    async def async_internal_added_to_hass(self) -> None:
        """Run when engine about to be added to Home Assistant.

        Not to be extended by integrations.
        """

    async def async_added_to_hass(self) -> None:
        """Run when engine about to be added to Home Assistant."""

    async def async_internal_will_remove_from_hass(self) -> None:
        """Prepare to remove the engine from Home Assistant.

        Not to be extended by integrations.
        """

    async def async_will_remove_from_hass(self) -> None:
        """Prepare to remove the engine from Home Assistant."""


_EngineT_co = TypeVar("_EngineT_co", bound=Engine, covariant=True)


class EnginePlatformModule(Protocol[_EngineT_co]):
    """Protocol type for engine platform modules."""

    async def async_setup_entry(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> _EngineT_co:
        """Set up an integration platform from a config entry."""


class EngineComponent(Generic[_EngineT_co]):
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
        self._engines: dict[str, _EngineT_co] = {}

    @callback
    def async_get_engine(self, config_entry_id: str) -> _EngineT_co | None:
        """Return a wrapped engine."""
        return self._engines.get(config_entry_id)

    @callback
    def async_get_engines(self) -> list[_EngineT_co]:
        """Return a wrapped engine."""
        return list(self._engines.values())

    async def async_setup_entry(self, config_entry: ConfigEntry) -> bool:
        """Set up a config entry."""
        platform = await async_prepare_setup_platform(
            self.hass, self.config, self.domain, config_entry.domain
        )

        if platform is None:
            return False

        key = config_entry.entry_id

        if key in self._engines:
            raise ValueError("Config entry has already been setup!")

        try:
            engine = await cast(
                EnginePlatformModule[_EngineT_co], platform
            ).async_setup_entry(self.hass, config_entry)
            await engine.async_internal_added_to_hass()
            await engine.async_added_to_hass()
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Error setting up entry %s", config_entry.entry_id)
            return False

        self._engines[key] = engine
        return True

    async def async_unload_entry(self, config_entry: ConfigEntry) -> bool:
        """Unload a config entry."""
        key = config_entry.entry_id

        if (engine := self._engines.pop(key, None)) is None:
            raise ValueError("Config entry was never loaded!")

        try:
            await engine.async_internal_will_remove_from_hass()
            await engine.async_will_remove_from_hass()
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Error unloading entry %s", config_entry.entry_id)
            return False

        return True
