"""Engine component helper."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from types import ModuleType
from typing import Generic, Protocol, TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_prepare_setup_platform

from . import discovery
from .typing import ConfigType, DiscoveryInfoType


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

    async def async_setup_platform(
        self,
        hass: HomeAssistant,
    ) -> _EngineT_co:
        """Set up an integration platform async."""


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

    @callback
    def async_setup_discovery(self) -> None:
        """Initialize the engine component discovery."""

        async def async_platform_discovered(
            platform: str, info: DiscoveryInfoType | None
        ) -> None:
            """Handle for discovered platform."""
            await self.async_setup_domain(platform)

        discovery.async_listen_platform(
            self.hass, self.domain, async_platform_discovered
        )

    async def async_setup_domain(self, domain: str) -> bool:
        """Set up an integration."""

        async def setup(platform: EnginePlatformModule[_EngineT_co]) -> _EngineT_co:
            return await platform.async_setup_platform(self.hass)

        return await self._async_do_setup(domain, domain, setup)

    async def async_setup_entry(self, config_entry: ConfigEntry) -> bool:
        """Set up a config entry."""

        async def setup(platform: EnginePlatformModule[_EngineT_co]) -> _EngineT_co:
            return await platform.async_setup_entry(self.hass, config_entry)

        return await self._async_do_setup(
            config_entry.entry_id, config_entry.domain, setup
        )

    async def _async_do_setup(
        self,
        key: str,
        platform_domain: str,
        get_setup_coro: Callable[[ModuleType], Awaitable[_EngineT_co]],
    ) -> bool:
        """Set up an entry."""
        platform = await async_prepare_setup_platform(
            self.hass, self.config, self.domain, platform_domain
        )

        if platform is None:
            return False

        if key in self._engines:
            raise ValueError("Config entry has already been setup!")

        try:
            engine = await get_setup_coro(platform)
            await engine.async_internal_added_to_hass()
            await engine.async_added_to_hass()
        except Exception:  # pylint: disable=broad-except
            self.logger.exception(
                "Error getting engine for %s (%s)", key, platform_domain
            )
            return False

        self._engines[key] = engine
        return True

    async def async_unload_domain(self, domain: str) -> bool:
        """Unload a domain."""
        return await self._async_do_unload(domain)

    async def async_unload_entry(self, config_entry: ConfigEntry) -> bool:
        """Unload a config entry."""
        return await self._async_do_unload(config_entry.entry_id)

    async def _async_do_unload(self, key: str) -> bool:
        """Unload an engine."""
        if (engine := self._engines.pop(key, None)) is None:
            raise ValueError("Config entry was never loaded!")

        try:
            await engine.async_internal_will_remove_from_hass()
            await engine.async_will_remove_from_hass()
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Error unloading entry %s", key)
            return False

        return True
