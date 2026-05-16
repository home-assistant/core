"""RemoteHostEntityPlatform for sandbox entities.

Instead of using per-domain platform files and async_forward_entry_setups,
the sandbox integration creates RemoteHostEntityPlatform instances directly
and adds them to the domain's EntityComponent. This platform manages proxy
entities that represent sandbox entities on the host.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import (
    DATA_DOMAIN_PLATFORM_ENTITIES,
    EntityPlatform,
)

from .entity import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity

_LOGGER = logging.getLogger(__name__)


class RemoteHostEntityPlatform(EntityPlatform):
    """EntityPlatform that manages proxy entities for a sandbox connection.

    Added directly to the domain's EntityComponent._platforms instead of
    being set up through the normal platform discovery mechanism.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        config_entry: ConfigEntry,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the remote host entity platform."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            domain=domain,
            platform_name="sandbox",
            platform=None,
            scan_interval=timedelta(seconds=0),
            entity_namespace=None,
        )
        self.config_entry = config_entry
        self._manager = manager
        self.parallel_updates_created = True

    async def async_add_proxy_entity(
        self, description: SandboxEntityDescription
    ) -> SandboxProxyEntity:
        """Create and add a proxy entity from a sandbox registration."""
        entity = self._manager.add_entity(description)
        await self.async_add_entities([entity])
        return entity


def async_get_or_create_host_platform(
    hass: HomeAssistant,
    domain: str,
    config_entry: ConfigEntry,
    manager: SandboxEntityManager,
) -> RemoteHostEntityPlatform:
    """Get or create a RemoteHostEntityPlatform for the given domain.

    Adds the platform to the domain's EntityComponent if it doesn't exist yet.
    """
    from homeassistant.helpers.entity_component import DATA_INSTANCES

    entity_components = hass.data.get(DATA_INSTANCES, {})
    component: EntityComponent[Any] | None = entity_components.get(domain)

    platform_key = f"sandbox_{config_entry.entry_id}"

    if component is not None:
        existing = component._platforms.get(platform_key)
        if isinstance(existing, RemoteHostEntityPlatform):
            return existing

    platform = RemoteHostEntityPlatform(
        hass=hass,
        domain=domain,
        config_entry=config_entry,
        manager=manager,
    )
    platform.async_prepare()

    if component is not None:
        component._platforms[platform_key] = platform

    return platform
