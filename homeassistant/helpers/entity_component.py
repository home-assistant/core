"""Helpers for components that manage entities."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import timedelta
import logging
from types import ModuleType
from typing import Any, Generic

from typing_extensions import TypeVar

from homeassistant import config as conf_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import (
    Event,
    HassJob,
    HassJobType,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_get_integration, bind_hass
from homeassistant.setup import async_prepare_setup_platform

from . import config_validation as cv, discovery, entity, service
from .entity_platform import EntityPlatform
from .typing import ConfigType, DiscoveryInfoType, VolDictType, VolSchemaType

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DATA_INSTANCES = "entity_components"

_EntityT = TypeVar("_EntityT", bound=entity.Entity, default=entity.Entity)


@bind_hass
async def async_update_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Trigger an update for an entity."""
    domain = entity_id.partition(".")[0]
    entity_comp: EntityComponent[entity.Entity] | None
    entity_comp = hass.data.get(DATA_INSTANCES, {}).get(domain)

    if entity_comp is None:
        logging.getLogger(__name__).warning(
            "Forced update failed. Component for %s not loaded.", entity_id
        )
        return

    if (entity_obj := entity_comp.get_entity(entity_id)) is None:
        logging.getLogger(__name__).warning(
            "Forced update failed. Entity %s not found.", entity_id
        )
        return

    await entity_obj.async_update_ha_state(True)


class EntityComponent(Generic[_EntityT]):
    """The EntityComponent manages platforms that manage entities.

    An example of an entity component is 'light', which manages platforms such
    as 'hue.light'.

    This class has the following responsibilities:
     - Process the configuration and set up a platform based component, for example light.
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
    ) -> None:
        """Initialize an entity component."""
        self.logger = logger
        self.hass = hass
        self.domain = domain
        self.scan_interval = scan_interval

        self.config: ConfigType | None = None

        domain_platform = self._async_init_entity_platform(domain, None)
        self._platforms: dict[
            str | tuple[str, timedelta | None, str | None], EntityPlatform
        ] = {domain: domain_platform}
        self.async_add_entities = domain_platform.async_add_entities
        self.add_entities = domain_platform.add_entities
        self._entities: dict[str, entity.Entity] = domain_platform.domain_entities
        hass.data.setdefault(DATA_INSTANCES, {})[domain] = self

    @property
    def entities(self) -> Iterable[_EntityT]:
        """Return an iterable that returns all entities.

        As the underlying dicts may change when async context is lost,
        callers that iterate over this asynchronously should make a copy
        using list() before iterating.
        """
        return self._entities.values()  # type: ignore[return-value]

    def get_entity(self, entity_id: str) -> _EntityT | None:
        """Get an entity."""
        return self._entities.get(entity_id)  # type: ignore[return-value]

    def register_shutdown(self) -> None:
        """Register shutdown on Home Assistant STOP event.

        Note: this is only required if the integration never calls
        `setup` or `async_setup`.
        """
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_shutdown)

    def setup(self, config: ConfigType) -> None:
        """Set up a full entity component.

        This doesn't block the executor to protect from deadlocks.
        """
        self.hass.create_task(
            self.async_setup(config), f"EntityComponent setup {self.domain}"
        )

    async def async_setup(self, config: ConfigType) -> None:
        """Set up a full entity component.

        Loads the platforms from the config and will listen for supported
        discovered platforms.

        This method must be run in the event loop.
        """
        self.register_shutdown()

        self.config = config

        # Look in config for Domain, Domain 2, Domain 3 etc and load them
        for p_type, p_config in conf_util.config_per_platform(config, self.domain):
            if p_type is not None:
                self.hass.async_create_task_internal(
                    self.async_setup_platform(p_type, p_config),
                    f"EntityComponent setup platform {p_type} {self.domain}",
                    eager_start=True,
                )

        # Generic discovery listener for loading platform dynamically
        # Refer to: homeassistant.helpers.discovery.async_load_platform()
        discovery.async_listen_platform(
            self.hass, self.domain, self._async_component_platform_discovered
        )

    async def _async_component_platform_discovered(
        self, platform: str, info: dict[str, Any] | None
    ) -> None:
        """Handle the loading of a platform."""
        await self.async_setup_platform(platform, {}, info)

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
            raise ValueError(
                f"Config entry {config_entry.title} ({key}) for "
                f"{platform_type}.{self.domain} has already been setup!"
            )

        self._platforms[key] = self._async_init_entity_platform(
            platform_type,
            platform,
            scan_interval=getattr(platform, "SCAN_INTERVAL", None),
        )

        return await self._platforms[key].async_setup_entry(config_entry)

    async def async_unload_entry(self, config_entry: ConfigEntry) -> bool:
        """Unload a config entry."""
        key = config_entry.entry_id

        if (platform := self._platforms.pop(key, None)) is None:
            raise ValueError("Config entry was never loaded!")

        await platform.async_reset()
        return True

    async def async_extract_from_service(
        self, service_call: ServiceCall, expand_group: bool = True
    ) -> list[_EntityT]:
        """Extract all known and available entities from a service call.

        Will return an empty list if entities specified but unknown.

        This method must be run in the event loop.
        """
        return await service.async_extract_entities(
            self.hass, self.entities, service_call, expand_group
        )

    @callback
    def async_register_legacy_entity_service(
        self,
        name: str,
        schema: VolDictType | VolSchemaType,
        func: str | Callable[..., Any],
        required_features: list[int] | None = None,
        supports_response: SupportsResponse = SupportsResponse.NONE,
    ) -> None:
        """Register an entity service with a legacy response format."""
        if isinstance(schema, dict):
            schema = cv.make_entity_service_schema(schema)

        service_func: str | HassJob[..., Any]
        service_func = func if isinstance(func, str) else HassJob(func)

        async def handle_service(
            call: ServiceCall,
        ) -> ServiceResponse:
            """Handle the service."""

            result = await service.entity_service_call(
                self.hass, self._entities, service_func, call, required_features
            )

            if result:
                if len(result) > 1:
                    raise HomeAssistantError(
                        "Deprecated service call matched more than one entity"
                    )
                return result.popitem()[1]
            return None

        self.hass.services.async_register(
            self.domain, name, handle_service, schema, supports_response
        )

    @callback
    def async_register_entity_service(
        self,
        name: str,
        schema: VolDictType | VolSchemaType | None,
        func: str | Callable[..., Any],
        required_features: list[int] | None = None,
        supports_response: SupportsResponse = SupportsResponse.NONE,
    ) -> None:
        """Register an entity service."""
        service.async_register_entity_service(
            self.hass,
            self.domain,
            name,
            entities=self._entities,
            func=func,
            job_type=HassJobType.Coroutinefunction,
            required_features=required_features,
            schema=schema,
            supports_response=supports_response,
        )

    async def async_setup_platform(
        self,
        platform_type: str,
        platform_config: ConfigType,
        discovery_info: DiscoveryInfoType | None = None,
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

        await self._platforms[key].async_setup(platform_config, discovery_info)

    async def _async_reset(self) -> None:
        """Remove entities and reset the entity component to initial values.

        This method must be run in the event loop.
        """
        tasks = []

        for key, platform in self._platforms.items():
            if key == self.domain:
                tasks.append(platform.async_reset())
            else:
                tasks.append(platform.async_destroy())

        if tasks:
            await asyncio.gather(*tasks)

        self._platforms = {self.domain: self._platforms[self.domain]}
        self.config = None

    async def async_remove_entity(self, entity_id: str) -> None:
        """Remove an entity managed by one of the platforms."""
        found = None

        for platform in self._platforms.values():
            if entity_id in platform.entities:
                found = platform
                break

        if found:
            await found.async_remove_entity(entity_id)

    async def async_prepare_reload(
        self, *, skip_reset: bool = False
    ) -> ConfigType | None:
        """Prepare reloading this entity component.

        This method must be run in the event loop.
        """
        try:
            conf = await conf_util.async_hass_config_yaml(self.hass)
        except HomeAssistantError as err:
            self.logger.error(err)
            return None

        integration = await async_get_integration(self.hass, self.domain)

        processed_conf = await conf_util.async_process_component_and_handle_errors(
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
        platform: ModuleType | None,
        scan_interval: timedelta | None = None,
        entity_namespace: str | None = None,
    ) -> EntityPlatform:
        """Initialize an entity platform."""
        if scan_interval is None:
            scan_interval = self.scan_interval

        entity_platform = EntityPlatform(
            hass=self.hass,
            logger=self.logger,
            domain=self.domain,
            platform_name=platform_type,
            platform=platform,
            scan_interval=scan_interval,
            entity_namespace=entity_namespace,
        )
        entity_platform.async_prepare()
        return entity_platform

    @callback
    def _async_shutdown(self, event: Event) -> None:
        """Call when Home Assistant is stopping."""
        for platform in self._platforms.values():
            platform.async_shutdown()
