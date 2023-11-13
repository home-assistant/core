"""Class to manage the entities for a single platform."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from contextvars import ContextVar
from datetime import datetime, timedelta
from logging import Logger, getLogger
from typing import TYPE_CHECKING, Any, Protocol

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_RESTORED,
    DEVICE_DEFAULT_NAME,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    CoreState,
    EntityServiceResponse,
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    callback,
    split_entity_id,
    valid_entity_id,
)
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.generated import languages
from homeassistant.setup import async_start_setup
from homeassistant.util.async_ import run_callback_threadsafe

from . import (
    config_validation as cv,
    device_registry as dev_reg,
    entity_registry as ent_reg,
    service,
    translation,
)
from .entity_registry import EntityRegistry, RegistryEntryDisabler, RegistryEntryHider
from .event import async_call_later, async_track_time_interval
from .issue_registry import IssueSeverity, async_create_issue
from .typing import UNDEFINED, ConfigType, DiscoveryInfoType

if TYPE_CHECKING:
    from .entity import Entity


SLOW_SETUP_WARNING = 10
SLOW_SETUP_MAX_WAIT = 60
SLOW_ADD_ENTITY_MAX_WAIT = 15  # Per Entity
SLOW_ADD_MIN_TIMEOUT = 500

PLATFORM_NOT_READY_RETRIES = 10
DATA_ENTITY_PLATFORM = "entity_platform"
PLATFORM_NOT_READY_BASE_WAIT_TIME = 30  # seconds

_LOGGER = getLogger(__name__)


class AddEntitiesCallback(Protocol):
    """Protocol type for EntityPlatform.add_entities callback."""

    def __call__(
        self, new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        """Define add_entities type."""


class EntityPlatformModule(Protocol):
    """Protocol type for entity platform modules."""

    async def async_setup_platform(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up an integration platform async."""

    def setup_platform(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up an integration platform."""

    async def async_setup_entry(
        self,
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up an integration platform from a config entry."""


class EntityPlatform:
    """Manage the entities for a single platform."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        logger: Logger,
        domain: str,
        platform_name: str,
        platform: EntityPlatformModule | None,
        scan_interval: timedelta,
        entity_namespace: str | None,
    ) -> None:
        """Initialize the entity platform."""
        self.hass = hass
        self.logger = logger
        self.domain = domain
        self.platform_name = platform_name
        self.platform = platform
        self.scan_interval = scan_interval
        self.entity_namespace = entity_namespace
        self.config_entry: config_entries.ConfigEntry | None = None
        self.entities: dict[str, Entity] = {}
        self.component_translations: dict[str, Any] = {}
        self.platform_translations: dict[str, Any] = {}
        self.object_id_component_translations: dict[str, Any] = {}
        self.object_id_platform_translations: dict[str, Any] = {}
        self._tasks: list[asyncio.Task[None]] = []
        # Stop tracking tasks after setup is completed
        self._setup_complete = False
        # Method to cancel the state change listener
        self._async_unsub_polling: CALLBACK_TYPE | None = None
        # Method to cancel the retry of setup
        self._async_cancel_retry_setup: CALLBACK_TYPE | None = None
        self._process_updates: asyncio.Lock | None = None

        self.parallel_updates: asyncio.Semaphore | None = None
        self._update_in_sequence: bool = False

        # Platform is None for the EntityComponent "catch-all" EntityPlatform
        # which powers entity_component.add_entities
        self.parallel_updates_created = platform is None

        hass.data.setdefault(DATA_ENTITY_PLATFORM, {}).setdefault(
            self.platform_name, []
        ).append(self)

    def __repr__(self) -> str:
        """Represent an EntityPlatform."""
        return (
            "<EntityPlatform "
            f"domain={self.domain} "
            f"platform_name={self.platform_name} "
            f"config_entry={self.config_entry}>"
        )

    @callback
    def _get_parallel_updates_semaphore(
        self, entity_has_sync_update: bool
    ) -> asyncio.Semaphore | None:
        """Get or create a semaphore for parallel updates.

        Semaphore will be created on demand because we base it off if update
        method is async or not.

        - If parallel updates is set to 0, we skip the semaphore.
        - If parallel updates is set to a number, we initialize the semaphore
          to that number.

        The default value for parallel requests is decided based on the first
        entity that is added to Home Assistant. It's 0 if the entity defines
        the async_update method, else it's 1.
        """
        if self.parallel_updates_created:
            return self.parallel_updates

        self.parallel_updates_created = True

        parallel_updates = getattr(self.platform, "PARALLEL_UPDATES", None)

        if parallel_updates is None and entity_has_sync_update:
            parallel_updates = 1

        if parallel_updates == 0:
            parallel_updates = None

        if parallel_updates is not None:
            self.parallel_updates = asyncio.Semaphore(parallel_updates)
            self._update_in_sequence = parallel_updates == 1

        return self.parallel_updates

    async def async_setup(
        self,
        platform_config: ConfigType,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up the platform from a config file."""
        platform = self.platform
        hass = self.hass

        if not hasattr(platform, "async_setup_platform") and not hasattr(
            platform, "setup_platform"
        ):
            self.logger.error(
                (
                    "The %s platform for the %s integration does not support platform"
                    " setup. Please remove it from your config."
                ),
                self.platform_name,
                self.domain,
            )
            learn_more_url = None
            if self.platform and "custom_components" not in self.platform.__file__:  # type: ignore[attr-defined]
                learn_more_url = (
                    f"https://www.home-assistant.io/integrations/{self.platform_name}/"
                )
            platform_key = f"platform: {self.platform_name}"
            yaml_example = f"```yaml\n{self.domain}:\n  - {platform_key}\n```"
            async_create_issue(
                self.hass,
                HOMEASSISTANT_DOMAIN,
                f"platform_integration_no_support_{self.domain}_{self.platform_name}",
                is_fixable=False,
                issue_domain=self.platform_name,
                learn_more_url=learn_more_url,
                severity=IssueSeverity.ERROR,
                translation_key="no_platform_setup",
                translation_placeholders={
                    "domain": self.domain,
                    "platform": self.platform_name,
                    "platform_key": platform_key,
                    "yaml_example": yaml_example,
                },
            )

            return

        @callback
        def async_create_setup_task() -> (
            Coroutine[Any, Any, None] | asyncio.Future[None]
        ):
            """Get task to set up platform."""
            if getattr(platform, "async_setup_platform", None):
                return platform.async_setup_platform(  # type: ignore[union-attr]
                    hass,
                    platform_config,
                    self._async_schedule_add_entities,
                    discovery_info,
                )

            # This should not be replaced with hass.async_add_job because
            # we don't want to track this task in case it blocks startup.
            return hass.loop.run_in_executor(
                None,
                platform.setup_platform,  # type: ignore[union-attr]
                hass,
                platform_config,
                self._schedule_add_entities,
                discovery_info,
            )

        await self._async_setup_platform(async_create_setup_task)

    async def async_shutdown(self) -> None:
        """Call when Home Assistant is stopping."""
        self.async_cancel_retry_setup()
        self.async_unsub_polling()

    @callback
    def async_cancel_retry_setup(self) -> None:
        """Cancel retry setup."""
        if self._async_cancel_retry_setup is not None:
            self._async_cancel_retry_setup()
            self._async_cancel_retry_setup = None

    async def async_setup_entry(self, config_entry: config_entries.ConfigEntry) -> bool:
        """Set up the platform from a config entry."""
        # Store it so that we can save config entry ID in entity registry
        self.config_entry = config_entry
        platform = self.platform

        @callback
        def async_create_setup_task() -> Coroutine[Any, Any, None]:
            """Get task to set up platform."""
            config_entries.current_entry.set(config_entry)

            return platform.async_setup_entry(  # type: ignore[union-attr]
                self.hass, config_entry, self._async_schedule_add_entities_for_entry
            )

        return await self._async_setup_platform(async_create_setup_task)

    async def _async_setup_platform(
        self, async_create_setup_task: Callable[[], Awaitable[None]], tries: int = 0
    ) -> bool:
        """Set up a platform via config file or config entry.

        async_create_setup_task creates a coroutine that sets up platform.
        """
        current_platform.set(self)
        logger = self.logger
        hass = self.hass
        full_name = f"{self.domain}.{self.platform_name}"
        object_id_language = (
            hass.config.language
            if hass.config.language in languages.NATIVE_ENTITY_IDS
            else languages.DEFAULT_LANGUAGE
        )

        async def get_translations(
            language: str, category: str, integration: str
        ) -> dict[str, Any]:
            """Get entity translations."""
            try:
                return await translation.async_get_translations(
                    hass, language, category, {integration}
                )
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.debug(
                    "Could not load translations for %s",
                    integration,
                    exc_info=err,
                )
            return {}

        self.component_translations = await get_translations(
            hass.config.language, "entity_component", self.domain
        )
        self.platform_translations = await get_translations(
            hass.config.language, "entity", self.platform_name
        )
        if object_id_language == hass.config.language:
            self.object_id_component_translations = self.component_translations
            self.object_id_platform_translations = self.platform_translations
        else:
            self.object_id_component_translations = await get_translations(
                object_id_language, "entity_component", self.domain
            )
            self.object_id_platform_translations = await get_translations(
                object_id_language, "entity", self.platform_name
            )

        logger.info("Setting up %s", full_name)
        warn_task = hass.loop.call_at(
            hass.loop.time() + SLOW_SETUP_WARNING,
            logger.warning,
            "Setup of %s platform %s is taking over %s seconds.",
            self.domain,
            self.platform_name,
            SLOW_SETUP_WARNING,
        )
        with async_start_setup(hass, [full_name]):
            try:
                task = async_create_setup_task()

                async with hass.timeout.async_timeout(SLOW_SETUP_MAX_WAIT, self.domain):
                    await asyncio.shield(task)

                # Block till all entities are done
                while self._tasks:
                    pending = [task for task in self._tasks if not task.done()]
                    self._tasks.clear()

                    if pending:
                        await asyncio.gather(*pending)

                hass.config.components.add(full_name)
                self._setup_complete = True
                return True
            except PlatformNotReady as ex:
                tries += 1
                wait_time = min(tries, 6) * PLATFORM_NOT_READY_BASE_WAIT_TIME
                message = str(ex)
                ready_message = f"ready yet: {message}" if message else "ready yet"
                if tries == 1:
                    logger.warning(
                        "Platform %s not %s; Retrying in background in %d seconds",
                        self.platform_name,
                        ready_message,
                        wait_time,
                    )
                else:
                    logger.debug(
                        "Platform %s not %s; Retrying in %d seconds",
                        self.platform_name,
                        ready_message,
                        wait_time,
                    )

                async def setup_again(*_args: Any) -> None:
                    """Run setup again."""
                    self._async_cancel_retry_setup = None
                    await self._async_setup_platform(async_create_setup_task, tries)

                if hass.state == CoreState.running:
                    self._async_cancel_retry_setup = async_call_later(
                        hass, wait_time, setup_again
                    )
                else:
                    self._async_cancel_retry_setup = hass.bus.async_listen_once(
                        EVENT_HOMEASSISTANT_STARTED, setup_again
                    )
                return False
            except asyncio.TimeoutError:
                logger.error(
                    (
                        "Setup of platform %s is taking longer than %s seconds."
                        " Startup will proceed without waiting any longer."
                    ),
                    self.platform_name,
                    SLOW_SETUP_MAX_WAIT,
                )
                return False
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "Error while setting up %s platform for %s",
                    self.platform_name,
                    self.domain,
                )
                return False
            finally:
                warn_task.cancel()

    def _schedule_add_entities(
        self, new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        """Schedule adding entities for a single platform, synchronously."""
        run_callback_threadsafe(
            self.hass.loop,
            self._async_schedule_add_entities,
            list(new_entities),
            update_before_add,
        ).result()

    @callback
    def _async_schedule_add_entities(
        self, new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        """Schedule adding entities for a single platform async."""
        task = self.hass.async_create_task(
            self.async_add_entities(new_entities, update_before_add=update_before_add),
            f"EntityPlatform async_add_entities {self.domain}.{self.platform_name}",
        )

        if not self._setup_complete:
            self._tasks.append(task)

    @callback
    def _async_schedule_add_entities_for_entry(
        self, new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        """Schedule adding entities for a single platform async and track the task."""
        assert self.config_entry
        task = self.config_entry.async_create_task(
            self.hass,
            self.async_add_entities(new_entities, update_before_add=update_before_add),
            f"EntityPlatform async_add_entities_for_entry {self.domain}.{self.platform_name}",
        )

        if not self._setup_complete:
            self._tasks.append(task)

    def add_entities(
        self, new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        """Add entities for a single platform."""
        # That avoid deadlocks
        if update_before_add:
            self.logger.warning(
                "Call 'add_entities' with update_before_add=True "
                "only inside tests or you can run into a deadlock!"
            )

        asyncio.run_coroutine_threadsafe(
            self.async_add_entities(list(new_entities), update_before_add),
            self.hass.loop,
        ).result()

    async def async_add_entities(
        self, new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        """Add entities for a single platform async.

        This method must be run in the event loop.
        """
        # handle empty list from component/platform
        if not new_entities:  # type: ignore[truthy-iterable]
            return

        hass = self.hass

        entity_registry = ent_reg.async_get(hass)
        tasks = [
            self._async_add_entity(entity, update_before_add, entity_registry)
            for entity in new_entities
        ]

        # No entities for processing
        if not tasks:
            return

        timeout = max(SLOW_ADD_ENTITY_MAX_WAIT * len(tasks), SLOW_ADD_MIN_TIMEOUT)
        try:
            async with self.hass.timeout.async_timeout(timeout, self.domain):
                await asyncio.gather(*tasks)
        except asyncio.TimeoutError:
            self.logger.warning(
                "Timed out adding entities for domain %s with platform %s after %ds",
                self.domain,
                self.platform_name,
                timeout,
            )
        except Exception:
            self.logger.exception(
                "Error adding entities for domain %s with platform %s",
                self.domain,
                self.platform_name,
            )
            raise

        if (
            (self.config_entry and self.config_entry.pref_disable_polling)
            or self._async_unsub_polling is not None
            or not any(entity.should_poll for entity in self.entities.values())
        ):
            return

        self._async_unsub_polling = async_track_time_interval(
            self.hass,
            self._update_entity_states,
            self.scan_interval,
            name=f"EntityPlatform poll {self.domain}.{self.platform_name}",
        )

    def _entity_id_already_exists(self, entity_id: str) -> tuple[bool, bool]:
        """Check if an entity_id already exists.

        Returns a tuple [already_exists, restored]
        """
        already_exists = entity_id in self.entities
        restored = False

        if not already_exists and not self.hass.states.async_available(entity_id):
            existing = self.hass.states.get(entity_id)
            if existing is not None and ATTR_RESTORED in existing.attributes:
                restored = True
            else:
                already_exists = True
        return (already_exists, restored)

    async def _async_add_entity(  # noqa: C901
        self,
        entity: Entity,
        update_before_add: bool,
        entity_registry: EntityRegistry,
    ) -> None:
        """Add an entity to the platform."""
        if entity is None:
            raise ValueError("Entity cannot be None")

        entity.add_to_platform_start(
            self.hass,
            self,
            self._get_parallel_updates_semaphore(hasattr(entity, "update")),
        )

        # Update properties before we generate the entity_id. This will happen
        # also for disabled entities.
        if update_before_add:
            try:
                await entity.async_device_update(warning=False)
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("%s: Error on device update!", self.platform_name)
                entity.add_to_platform_abort()
                return

        suggested_object_id: str | None = None
        generate_new_entity_id = False

        entity_name = entity.name
        if entity_name is UNDEFINED:
            entity_name = None

        # Get entity_id from unique ID registration
        if entity.unique_id is not None:
            registered_entity_id = entity_registry.async_get_entity_id(
                self.domain, self.platform_name, entity.unique_id
            )
            if registered_entity_id:
                already_exists, _ = self._entity_id_already_exists(registered_entity_id)

                if already_exists:
                    # If there's a collision, the entry belongs to another entity
                    entity.registry_entry = None
                    msg = (
                        f"Platform {self.platform_name} does not generate unique IDs. "
                    )
                    if entity.entity_id:
                        msg += (
                            f"ID {entity.unique_id} is already used by"
                            f" {registered_entity_id} - ignoring {entity.entity_id}"
                        )
                    else:
                        msg += (
                            f"ID {entity.unique_id} already exists - ignoring"
                            f" {registered_entity_id}"
                        )
                    self.logger.error(msg)
                    entity.add_to_platform_abort()
                    return

            if self.config_entry and (device_info := entity.device_info):
                try:
                    device = dev_reg.async_get(self.hass).async_get_or_create(
                        config_entry_id=self.config_entry.entry_id,
                        **device_info,
                    )
                except dev_reg.DeviceInfoError as exc:
                    self.logger.error(
                        "%s: Not adding entity with invalid device info: %s",
                        self.platform_name,
                        str(exc),
                    )
                    entity.add_to_platform_abort()
                    return
            else:
                device = None

            # An entity may suggest the entity_id by setting entity_id itself
            suggested_entity_id: str | None = entity.entity_id
            if suggested_entity_id is not None:
                suggested_object_id = split_entity_id(entity.entity_id)[1]
            else:
                if device and entity.has_entity_name:
                    device_name = device.name_by_user or device.name
                    if entity.use_device_name:
                        suggested_object_id = device_name
                    else:
                        suggested_object_id = (
                            f"{device_name} {entity.suggested_object_id}"
                        )
                if not suggested_object_id:
                    suggested_object_id = entity.suggested_object_id

            if self.entity_namespace is not None:
                suggested_object_id = f"{self.entity_namespace} {suggested_object_id}"

            disabled_by: RegistryEntryDisabler | None = None
            if not entity.entity_registry_enabled_default:
                disabled_by = RegistryEntryDisabler.INTEGRATION

            hidden_by: RegistryEntryHider | None = None
            if not entity.entity_registry_visible_default:
                hidden_by = RegistryEntryHider.INTEGRATION

            entry = entity_registry.async_get_or_create(
                self.domain,
                self.platform_name,
                entity.unique_id,
                capabilities=entity.capability_attributes,
                config_entry=self.config_entry,
                device_id=device.id if device else None,
                disabled_by=disabled_by,
                entity_category=entity.entity_category,
                get_initial_options=entity.get_initial_entity_options,
                has_entity_name=entity.has_entity_name,
                hidden_by=hidden_by,
                known_object_ids=self.entities.keys(),
                original_device_class=entity.device_class,
                original_icon=entity.icon,
                original_name=entity_name,
                suggested_object_id=suggested_object_id,
                supported_features=entity.supported_features,
                translation_key=entity.translation_key,
                unit_of_measurement=entity.unit_of_measurement,
            )

            if device and device.disabled and not entry.disabled:
                entry = entity_registry.async_update_entity(
                    entry.entity_id, disabled_by=RegistryEntryDisabler.DEVICE
                )

            entity.registry_entry = entry
            if device:
                entity.device_entry = device
            entity.entity_id = entry.entity_id

        # We won't generate an entity ID if the platform has already set one
        # We will however make sure that platform cannot pick a registered ID
        elif entity.entity_id is not None and entity_registry.async_is_registered(
            entity.entity_id
        ):
            # If entity already registered, convert entity id to suggestion
            suggested_object_id = split_entity_id(entity.entity_id)[1]
            generate_new_entity_id = True

        # Generate entity ID
        if entity.entity_id is None or generate_new_entity_id:
            suggested_object_id = (
                suggested_object_id or entity.suggested_object_id or DEVICE_DEFAULT_NAME
            )

            if self.entity_namespace is not None:
                suggested_object_id = f"{self.entity_namespace} {suggested_object_id}"
            entity.entity_id = entity_registry.async_generate_entity_id(
                self.domain, suggested_object_id, self.entities.keys()
            )

        # Make sure it is valid in case an entity set the value themselves
        if not valid_entity_id(entity.entity_id):
            entity.add_to_platform_abort()
            raise HomeAssistantError(f"Invalid entity ID: {entity.entity_id}")

        already_exists, restored = self._entity_id_already_exists(entity.entity_id)

        if already_exists:
            self.logger.error(
                "Entity id already exists - ignoring: %s", entity.entity_id
            )
            entity.add_to_platform_abort()
            return

        if entity.registry_entry and entity.registry_entry.disabled:
            self.logger.debug(
                "Not adding entity %s because it's disabled",
                entry.name
                or entity_name
                or f'"{self.platform_name} {entity.unique_id}"',
            )
            entity.add_to_platform_abort()
            return

        entity_id = entity.entity_id
        self.entities[entity_id] = entity

        if not restored:
            # Reserve the state in the state machine
            # because as soon as we return control to the event
            # loop below, another entity could be added
            # with the same id before `entity.add_to_platform_finish()`
            # has a chance to finish.
            self.hass.states.async_reserve(entity.entity_id)

        def remove_entity_cb() -> None:
            """Remove entity from entities dict."""
            self.entities.pop(entity_id)

        entity.async_on_remove(remove_entity_cb)

        await entity.add_to_platform_finish()

    async def async_reset(self) -> None:
        """Remove all entities and reset data.

        This method must be run in the event loop.
        """
        self.async_cancel_retry_setup()

        if not self.entities:
            return

        tasks = [entity.async_remove() for entity in self.entities.values()]

        await asyncio.gather(*tasks)

        self.async_unsub_polling()
        self._setup_complete = False

    @callback
    def async_unsub_polling(self) -> None:
        """Stop polling."""
        if self._async_unsub_polling is not None:
            self._async_unsub_polling()
            self._async_unsub_polling = None

    async def async_destroy(self) -> None:
        """Destroy an entity platform.

        Call before discarding the object.
        """
        await self.async_reset()
        self.hass.data[DATA_ENTITY_PLATFORM][self.platform_name].remove(self)

    async def async_remove_entity(self, entity_id: str) -> None:
        """Remove entity id from platform."""
        await self.entities[entity_id].async_remove()

        # Clean up polling job if no longer needed
        if self._async_unsub_polling is not None and not any(
            entity.should_poll for entity in self.entities.values()
        ):
            self._async_unsub_polling()
            self._async_unsub_polling = None

    async def async_extract_from_service(
        self, service_call: ServiceCall, expand_group: bool = True
    ) -> list[Entity]:
        """Extract all known and available entities from a service call.

        Will return an empty list if entities specified but unknown.

        This method must be run in the event loop.
        """
        return await service.async_extract_entities(
            self.hass, self.entities.values(), service_call, expand_group
        )

    @callback
    def async_register_entity_service(
        self,
        name: str,
        schema: dict[str, Any] | vol.Schema,
        func: str | Callable[..., Any],
        required_features: Iterable[int] | None = None,
        supports_response: SupportsResponse = SupportsResponse.NONE,
    ) -> None:
        """Register an entity service.

        Services will automatically be shared by all platforms of the same domain.
        """
        if self.hass.services.has_service(self.platform_name, name):
            return

        if isinstance(schema, dict):
            schema = cv.make_entity_service_schema(schema)

        async def handle_service(call: ServiceCall) -> EntityServiceResponse | None:
            """Handle the service."""
            return await service.entity_service_call(
                self.hass,
                [
                    plf
                    for plf in self.hass.data[DATA_ENTITY_PLATFORM][self.platform_name]
                    if plf.domain == self.domain
                ],
                func,
                call,
                required_features,
            )

        self.hass.services.async_register(
            self.platform_name, name, handle_service, schema, supports_response
        )

    async def _update_entity_states(self, now: datetime) -> None:
        """Update the states of all the polling entities.

        To protect from flooding the executor, we will update async entities
        in parallel and other entities sequential.

        This method must be run in the event loop.
        """
        if self._process_updates is None:
            self._process_updates = asyncio.Lock()
        if self._process_updates.locked():
            self.logger.warning(
                "Updating %s %s took longer than the scheduled update interval %s",
                self.platform_name,
                self.domain,
                self.scan_interval,
            )
            return

        async with self._process_updates:
            if self._update_in_sequence or len(self.entities) <= 1:
                # If we know we will update sequentially, we want to avoid scheduling
                # the coroutines as tasks that will wait on the semaphore lock.
                for entity in list(self.entities.values()):
                    # If the entity is removed from hass during the previous
                    # entity being updated, we need to skip updating the
                    # entity.
                    if entity.should_poll and entity.hass:
                        await entity.async_update_ha_state(True)
                return

            if tasks := [
                entity.async_update_ha_state(True)
                for entity in self.entities.values()
                if entity.should_poll
            ]:
                await asyncio.gather(*tasks)


current_platform: ContextVar[EntityPlatform | None] = ContextVar(
    "current_platform", default=None
)


@callback
def async_get_current_platform() -> EntityPlatform:
    """Get the current platform from context."""
    if (platform := current_platform.get()) is None:
        raise RuntimeError("Cannot get non-set current platform")
    return platform


@callback
def async_get_platforms(
    hass: HomeAssistant, integration_name: str
) -> list[EntityPlatform]:
    """Find existing platforms."""
    if (
        DATA_ENTITY_PLATFORM not in hass.data
        or integration_name not in hass.data[DATA_ENTITY_PLATFORM]
    ):
        return []

    platforms: list[EntityPlatform] = hass.data[DATA_ENTITY_PLATFORM][integration_name]

    return platforms
