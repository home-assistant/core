"""Network helper class for the network integration."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.core import HomeAssistant, callback

from .const import (
    ATTR_CONFIGURED_ADAPTERS,
    DEFAULT_CONFIGURED_ADAPTERS,
    NETWORK_CONFIG_SCHEMA,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .models import Adapter
from .util import (
    adapters_with_exernal_addresses,
    async_default_next_broadcast_hop,
    enable_adapters,
    enable_auto_detected_adapters,
    load_adapters,
)

ZC_CONF_DEFAULT_INTERFACE = (
    "default_interface"  # cannot import from zeroconf due to circular dep
)


class Network:
    """Network helper class for the network integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Network class."""
        self.hass = hass
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {}
        self._adapters: list[Adapter] = []
        self._next_broadcast_hop: str | None = None

    @property
    def adapters(self) -> list[Adapter]:
        """Return the list of adapters."""
        return self._adapters

    @property
    def configured_adapters(self) -> list[str]:
        """Return the configured adapters."""
        return self._data.get(ATTR_CONFIGURED_ADAPTERS, DEFAULT_CONFIGURED_ADAPTERS)

    async def async_setup(self) -> None:
        """Set up the network config."""
        self._next_broadcast_hop = await async_default_next_broadcast_hop(self.hass)
        await self.async_load()
        self._adapters = load_adapters(self._next_broadcast_hop)

    async def async_migrate_from_zeroconf(self, zc_config: dict[str, Any]) -> None:
        """Migrate configuration from zeroconf."""
        if self._data:
            return

        if (
            ZC_CONF_DEFAULT_INTERFACE in zc_config
            and not zc_config[ZC_CONF_DEFAULT_INTERFACE]
        ):
            self._data[ATTR_CONFIGURED_ADAPTERS] = adapters_with_exernal_addresses(
                self._adapters
            )
            await self._async_save()

    @callback
    def async_configure(self) -> None:
        """Configure from storage."""
        if not enable_adapters(self._adapters, self.configured_adapters):
            enable_auto_detected_adapters(self._adapters)

    async def async_reconfig(self, config: dict[str, Any]) -> None:
        """Reconfigure network."""
        config = NETWORK_CONFIG_SCHEMA(config)
        self._data[ATTR_CONFIGURED_ADAPTERS] = config[ATTR_CONFIGURED_ADAPTERS]
        enable_adapters(self._adapters, self.configured_adapters)
        await self._async_save()

    async def async_load(self) -> None:
        """Load config."""
        if stored := await self._store.async_load():
            self._data = cast(dict, stored)

    async def _async_save(self) -> None:
        """Save preferences."""
        await self._store.async_save(self._data)
