"""Helpers for components that manage entities."""
import asyncio
from datetime import timedelta
from itertools import chain
import logging
from types import ModuleType
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

import voluptuous as vol

from homeassistant import config as conf_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_per_platform,
    config_validation as cv,
    discovery,
    entity,
    service,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.loader import async_get_integration, bind_hass
from homeassistant.setup import async_prepare_setup_platform

from .entity_platform import EntityPlatform

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DATA_INSTANCES = "entity_components"


@bind_hass
async def async_update_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Trigger an update for an entity."""
    domain = entity_id.split(".", 1)[0]
    entity_comp = hass.data.get(DATA_INSTANCES, {}).get(domain)

    if entity_comp is None:
        logging.getLogger(__name__).warning(
            "Forced update failed. Component for %s not loaded.", entity_id
        )
        return

    entity_obj = entity_comp.get_entity(entity_id)

    if entity_obj is None:
        logging.getLogger(__name__).warning(
            "Forced update failed. Entity %s not found.", entity_id
        )
        return

    await entity_obj.async_update_ha_state(True)


class EntityComponent:
    """The EntityComponent manages platforms that manages entities.

    This class has the following responsibilities:
     - Process the configuration and set up a platform based component.
     - Manage the platforms and their entities.
     - Help extract the entities from a service call.
     - Listen for discovery events for platforms related to the domain.
    """

    def __init__(
        self,
        logger: logging.Logger,
        domain: str,
        hass: HomeAssistant,
        scan_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ):
        """Initialize an entity component."""
        self.logger = logger
        self.hass = hass
        self.domain = domain
        self.scan_interval = scan_interval

        self.config: Optional[ConfigType] = None

        self._platforms: Dict[
            Union[str, Tuple[str, Optional[timedelta], Optional[str]]], EntityPlatform
        ] = {domain: self._async_init_entity_platform(domain, None)}
        self.async_add_entities = self._platforms[domain].async_add_entities
        self.add_entities = self._platforms[domain].add_entities

        hass.data.setdefault(DATA_INSTANCES, {})[domain] = self

    @property
    def entities(self) -> Iterable[entity.Entity]:
        """Return an iterable that returns all entities."""
        return chain.from_iterable(
            platform.entities.values() for platform in self._platforms.values()
        )

    def get_entity(self, entity_id: str) -> Optional[entity.Entity]:
        """Get an entity."""
        for platform in self._platforms.values():
            entity_obj = platform.entities.get(entity_id)
            if entity_obj is not None:
                return entity_obj
        return None

    def setup(self, config: ConfigType) -> None:
        """Set up a full entity component.

        This doesn't block the executor to protect from deadlocks.
        """
        self.hass.add_job(
            self.async_setup(  # type: ignore
                config
            )
        )

    async def async_setup(self, config: ConfigType) -> None:
        """Set up a full entity component.

        Loads the platforms from the config and will listen for supported
        discovered platforms.

        This method must be run in the event loop.
        """
        self.config = config

        # Look in config for Domain, Domain 2, Domain 3 etc and load them
        tasks = []
        for p_type, p_config in config_per_platform(config, self.domain):
            tasks.append(self.async_setup_platform(p_type, p_config))

        if tasks:
            await asyncio.wait(tasks)

        # Generic discovery listener for loading platform dynamically
        # Refer to: homeassistant.components.discovery.load_platform()
        async def component_platform_discovered(
            platform: str, info: Optional[Dict[str, Any]]
        ) -> None:
            """Handle the loading of a platform."""
            await self.async_setup_platform(platform, {}, info)

        discovery.async_listen_platform(
            self.hass, self.domain, component_platform_discovered
        )

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

        self._platforms[key] = self._async_init_entity_platform(
            platform_type,
            platform,
            scan_interval=getattr(platform, "SCAN_INTERVAL", None),
        )

        return await self._platforms[key].async_setup_entry(config_entry)  # type: ignore

    async def async_unload_entry(self, config_entry: ConfigEntry) -> bool:
        """Unload a config entry."""
        key = config_entry.entry_id

        platform = self._platforms.pop(key, None)

        if platform is None:
            raise ValueError("Config entry was never loaded!")

        await platform.async_reset()
        return True

    async def async_extract_from_service(
        self, service_call: ServiceCall, expand_group: bool = True
    ) -> List[entity.Entity]:
        """Extract all known and available entities from a service call.

        Will return an empty list if entities specified but unknown.

        This method must be run in the event loop.
        """
        return await service.async_extract_entities(  # type: ignore
            self.hass, self.entities, service_call, expand_group
        )

    @callback
    def async_register_entity_service(
        self,
        name: str,
        schema: Union[Dict[str, Any], vol.Schema],
        func: str,
        required_features: Optional[int] = None,
    ) -> None:
        """Register an entity service."""
        if isinstance(schema, dict):
            schema = cv.make_entity_service_schema(schema)

        async def handle_service(call: Callable) -> None:
            """Handle the service."""
            await self.hass.helpers.service.entity_service_call(
                self._platforms.values(), func, call, required_features
            )

        self.hass.services.async_register(self.domain, name, handle_service, schema)

    async def async_setup_platform(
        self,
        platform_type: str,
        platform_config: ConfigType,
        discovery_info: Optional[DiscoveryInfoType] = None,
    ) -> None:
        """Set up a platform for this component."""
        if self.config is None:
            raise RuntimeError("async_setup needs to be called first")

        platform = await async_prepare_setup_platform(
            self.hass, self.config, self.domain, platform_type
        )

        if platform is None:
            return

        # Use config scan interval, fallback to platform if none set
        scan_interval = platform_config.get(
            CONF_SCAN_INTERVAL, getattr(platform, "SCAN_INTERVAL", None)
        )
        entity_namespace = platform_config.get(CONF_ENTITY_NAMESPACE)

        key = (platform_type, scan_interval, entity_namespace)

        if key not in self._platforms:
            self._platforms[key] = self._async_init_entity_platform(
                platform_type, platform, scan_interval, entity_namespace
            )

        await self._platforms[key].async_setup(  # type: ignore
            platform_config, discovery_info
        )

    async def _async_reset(self) -> None:
        """Remove entities and reset the entity component to initial values.

        This method must be run in the event loop.
        """
        tasks = [platform.async_reset() for platform in self._platforms.values()]

        if tasks:
            await asyncio.wait(tasks)

        self._platforms = {self.domain: self._platforms[self.domain]}
        self.config = None

    async def async_remove_entity(self, entity_id: str) -> None:
        """Remove an entity managed by one of the platforms."""
        for platform in self._platforms.values():
            if entity_id in platform.entities:
                await platform.async_remove_entity(entity_id)

    async def async_prepare_reload(self, *, skip_reset: bool = False) -> Optional[dict]:
        """Prepare reloading this entity component.

        This method must be run in the event loop.
        """
        try:
            conf = await conf_util.async_hass_config_yaml(self.hass)
        except HomeAssistantError as err:
            self.logger.error(err)
            return None

        integration = await async_get_integration(self.hass, self.domain)

        processed_conf = await conf_util.async_process_component_config(
            self.hass, conf, integration
        )

        if processed_conf is None:
            return None

        if not skip_reset:
            await self._async_reset()

        return processed_conf

    @callback
    def _async_init_entity_platform(
        self,
        platform_type: str,
        platform: Optional[ModuleType],
        scan_interval: Optional[timedelta] = None,
        entity_namespace: Optional[str] = None,
    ) -> EntityPlatform:
        """Initialize an entity platform."""
        if scan_interval is None:
            scan_interval = self.scan_interval

        return EntityPlatform(
            hass=self.hass,
            logger=self.logger,
            domain=self.domain,
            platform_name=platform_type,
            platform=platform,
            scan_interval=scan_interval,
            entity_namespace=entity_namespace,
        )
