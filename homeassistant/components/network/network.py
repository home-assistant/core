"""Network helper class for the network integration."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.core import HomeAssistant, callback

from .const import (
    ATTR_CONFIGURED_ADAPTERS,
    DEFAULT_CONFIGURED_ADAPTERS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .models import Adapter
from .util import (
    adapters_with_exernal_addresses,
    async_load_adapters,
    enable_adapters,
    enable_auto_detected_adapters,
)


class Network:
    """Network helper class for the network integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Network class."""
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {}
        self.adapters: list[Adapter] = []

    @property
    def configured_adapters(self) -> list[str]:
        """Return the configured adapters."""
        return self._data.get(ATTR_CONFIGURED_ADAPTERS, DEFAULT_CONFIGURED_ADAPTERS)

    async def async_setup(self) -> None:
        """Set up the network config."""
        await self.async_load()
        self.adapters = await async_load_adapters()

    async def async_migrate_from_zeroconf(self, zc_config: dict[str, Any]) -> None:
        """Migrate configuration from zeroconf."""
        if self._data or not zc_config:
            return

        from homeassistant.components.zeroconf import (  # pylint: disable=import-outside-toplevel
            CONF_DEFAULT_INTERFACE,
        )

        if zc_config.get(CONF_DEFAULT_INTERFACE) is False:
            self._data[ATTR_CONFIGURED_ADAPTERS] = adapters_with_exernal_addresses(
                self.adapters
            )
            await self._async_save()

    @callback
    def async_configure(self) -> None:
        """Configure from storage."""
        if not enable_adapters(self.adapters, self.configured_adapters):
            enable_auto_detected_adapters(self.adapters)

    async def async_reconfig(self, config: dict[str, Any]) -> None:
        """Reconfigure network."""
        self._data[ATTR_CONFIGURED_ADAPTERS] = config[ATTR_CONFIGURED_ADAPTERS]
        self.async_configure()
        await self._async_save()

    async def async_load(self) -> None:
        """Load config."""
        if stored := await self._store.async_load():
            self._data = cast(dict, stored)

    async def _async_save(self) -> None:
        """Save preferences."""
        await self._store.async_save(self._data)
