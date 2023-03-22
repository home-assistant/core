"""Network helper class for the network integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store

from .const import (
    ATTR_CONFIGURED_ADAPTERS,
    DATA_NETWORK,
    DEFAULT_CONFIGURED_ADAPTERS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .models import Adapter
from .util import async_load_adapters, enable_adapters, enable_auto_detected_adapters

_LOGGER = logging.getLogger(__name__)


@singleton(DATA_NETWORK)
async def async_get_network(hass: HomeAssistant) -> Network:
    """Get network singleton."""
    network = Network(hass)
    await network.async_setup()
    network.async_configure()

    _LOGGER.debug("Adapters: %s", network.adapters)
    return network


class Network:
    """Network helper class for the network integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Network class."""
        self._store = Store[dict[str, list[str]]](
            hass, STORAGE_VERSION, STORAGE_KEY, atomic_writes=True
        )
        self._data: dict[str, list[str]] = {}
        self.adapters: list[Adapter] = []

    @property
    def configured_adapters(self) -> list[str]:
        """Return the configured adapters."""
        return self._data.get(ATTR_CONFIGURED_ADAPTERS, DEFAULT_CONFIGURED_ADAPTERS)

    async def async_setup(self) -> None:
        """Set up the network config."""
        await self.async_load()
        self.adapters = await async_load_adapters()

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
            self._data = stored

    async def _async_save(self) -> None:
        """Save preferences."""
        await self._store.async_save(self._data)
