"""Helpers for integrations that manage services."""
from __future__ import annotations

from collections.abc import Iterable
from itertools import chain
import logging
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.setup import async_prepare_setup_platform

from .service_platform import PlatformService, ServicePlatform, ServicePlatformModule
from .typing import ConfigType

DATA_INSTANCES = "service_integrations"


class ServiceIntegration:
    """The ServiceIntegration manages platforms and their services."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        domain: str,
        config: ConfigType,
    ) -> None:
        """Initialize a service integration."""
        self.hass = hass
        self.config: ConfigType = config
        self.domain = domain
        self.logger = logger

        self._platforms: dict[str, ServicePlatform] = {}

        hass.data.setdefault(DATA_INSTANCES, {})[domain] = self

    @property
    def services(self) -> Iterable[PlatformService]:
        """Return an iterable that returns all services."""
        return chain.from_iterable(
            platform.services.values() for platform in self._platforms.values()
        )

    async def async_setup(self) -> None:
        """Set up a full service integration."""
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_shutdown)

    async def async_setup_entry(self, config_entry: ConfigEntry) -> bool:
        """Set up a config entry."""
        platform_type = config_entry.domain
        platform = await async_prepare_setup_platform(
            self.hass,
            self.config,
            self.domain,
            platform_type,
        )

        if platform is None:
            return False

        key = config_entry.entry_id

        if key in self._platforms:
            raise ValueError("Config entry has already been setup!")

        self._platforms[key] = ServicePlatform(
            hass=self.hass,
            logger=self.logger,
            domain=self.domain,
            platform_name=platform_type,
            platform=cast(ServicePlatformModule, platform),
        )

        return await self._platforms[key].async_setup_entry(config_entry)

    async def async_unload_entry(self, config_entry: ConfigEntry) -> bool:
        """Unload a config entry."""
        key = config_entry.entry_id

        platform = self._platforms.pop(key, None)

        if platform is None:
            raise ValueError("Config entry was never loaded!")

        platform.async_destroy()
        return True

    @callback
    def _async_shutdown(self, event: Event) -> None:
        """Call when Home Assistant is stopping."""
        for platform in self._platforms.values():
            platform.async_shutdown()
