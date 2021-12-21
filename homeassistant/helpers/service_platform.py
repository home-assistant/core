"""Manage the services for a single platform."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from dataclasses import dataclass
from logging import Logger
from typing import Any, Dict, Protocol, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, current_entry
from homeassistant.const import CONF_DESCRIPTION, CONF_NAME, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_start_setup

from .event import async_call_later
from .service import (
    async_set_service_schema,
    integration_service_call,
    load_services_file,
)

CONF_FIELDS = "fields"

SLOW_SETUP_WARNING = 10
SLOW_SETUP_MAX_WAIT = 60
SLOW_ADD_SERVICE_MAX_WAIT = 15  # Per PlatformService
SLOW_ADD_MIN_TIMEOUT = 500

DATA_SERVICE_PLATFORM = "service_platform"
DATA_SERVICE_PLATFORM_LOCKS = "service_platform_locks"
PLATFORM_NOT_READY_BASE_WAIT_TIME = 30  # seconds


class ServicePlatformModule(Protocol):
    """Protocol type for a platform using the ServicePlatform helper."""

    async def async_setup_entry(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_services: AddServicesCallback,
    ) -> None:
        """Set up the config entry for the service platform."""


class AddServicesCallback(Protocol):
    """Protocol type for ServicePlatform.async_add_services callback."""

    def __call__(self, new_services: Iterable[PlatformService]) -> None:
        """Define async_add_services type."""


class PlatformService(ABC):
    """Represent the service of a service integration platform."""

    # While not purely typed, it makes typehinting more useful for us
    # and removes the need for constant None checks or asserts.
    hass: HomeAssistant = None  # type: ignore
    platform: ServicePlatform = None  # type: ignore

    is_async: bool = False
    parallel_updates: asyncio.Semaphore | None = None
    _added: bool = False
    # Hold list for functions to call on remove.
    _on_remove: list[CALLBACK_TYPE] | None = None

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the name of the service, not including domain."""

    @property
    @abstractmethod
    def service_description(self) -> ServiceDescription:
        """Return the service description."""

    @property
    @abstractmethod
    def service_schema(self) -> vol.Schema:
        """Return the service schema."""

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: ServicePlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding a service to a platform."""
        self.hass = hass
        self.platform = platform
        self.parallel_updates = parallel_updates

        if self._added:
            raise HomeAssistantError(
                f"Service {self.service_name} cannot be added a second time to a service platform"
            )

        self._added = True

    @callback
    def add_to_platform_abort(self) -> None:
        """Abort adding a service to a platform."""
        self.hass = None  # type: ignore
        self.platform = None  # type: ignore
        self.parallel_updates = None
        self._added = False

    @callback
    def async_remove(self) -> None:
        """Remove service from Home Assistant."""
        if self.platform and not self._added:
            raise HomeAssistantError(
                f"Service {self.service_name} async_remove called twice"
            )

        self._added = False

        if self._on_remove is not None:
            while self._on_remove:
                self._on_remove.pop()()

    @callback
    def async_on_remove(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when service removed."""
        if self._on_remove is None:
            self._on_remove = []
        self._on_remove.append(func)

    async def async_request_call(self, coro: Awaitable) -> None:
        """Process request batched."""
        if self.parallel_updates:
            await self.parallel_updates.acquire()

        try:
            await coro
        finally:
            if self.parallel_updates:
                self.parallel_updates.release()

    @abstractmethod
    async def async_handle_service(self, service_call: ServiceCall) -> None:
        """Handle the service call."""


class ServicePlatform:
    """Manage the services for a single platform."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        logger: Logger,
        domain: str,
        platform_name: str,
        platform: ServicePlatformModule,
    ) -> None:
        """Initialize the service platform."""
        self.hass = hass
        self.logger = logger
        self.domain = domain
        self.platform_name = platform_name
        self.platform = platform
        self.config_entry: ConfigEntry | None = None
        self.services: dict[str, PlatformService] = {}
        self._tasks: list[asyncio.Task] = []
        # Stop tracking tasks after setup is completed
        self._setup_complete = False
        # Method to cancel the retry of setup
        self._async_cancel_retry_setup: CALLBACK_TYPE | None = None

        self.parallel_updates: asyncio.Semaphore | None = None
        self.parallel_updates_created = False

        hass.data.setdefault(DATA_SERVICE_PLATFORM, {}).setdefault(
            self.platform_name, []
        ).append(self)
        hass.data.setdefault(DATA_SERVICE_PLATFORM_LOCKS, {})

    def __repr__(self) -> str:
        """Represent a ServicePlatform."""
        return f"<ServicePlatform domain={self.domain} platform_name={self.platform_name} config_entry={self.config_entry}>"

    @callback
    def _get_parallel_updates_semaphore(
        self, service_is_async: bool
    ) -> asyncio.Semaphore | None:
        """Get or create a semaphore for parallel updates.

        Semaphore will be created on demand because we base it off if update method is async or not.

        If parallel updates is set to 0, we skip the semaphore.
        If parallel updates is set to a number, we initialize the semaphore to that number.
        The default value for parallel requests is decided based on the first service that is added to Home Assistant.
        It's 1 by default.
        """
        if self.parallel_updates_created:
            return self.parallel_updates

        self.parallel_updates_created = True

        parallel_updates = getattr(self.platform, "PARALLEL_UPDATES", None)

        if parallel_updates is None and not service_is_async:
            parallel_updates = 1

        if parallel_updates == 0:
            parallel_updates = None

        if parallel_updates is not None:
            self.parallel_updates = asyncio.Semaphore(parallel_updates)

        return self.parallel_updates

    @callback
    def async_shutdown(self) -> None:
        """Call when Home Assistant is stopping."""
        self.async_cancel_retry_setup()

    @callback
    def async_cancel_retry_setup(self) -> None:
        """Cancel retry setup."""
        if self._async_cancel_retry_setup is not None:
            self._async_cancel_retry_setup()
            self._async_cancel_retry_setup = None

    async def async_setup_entry(self, config_entry: ConfigEntry) -> bool:
        """Set up the platform from a config entry."""
        self.config_entry = config_entry
        platform = self.platform

        @callback
        def async_create_setup_task() -> Coroutine:
            """Get task to set up platform."""
            current_entry.set(config_entry)
            return platform.async_setup_entry(
                self.hass, config_entry, self._async_schedule_add_services
            )

        return await self._async_setup_platform(async_create_setup_task)

    async def _async_setup_platform(
        self, async_create_setup_task: Callable[[], Coroutine], tries: int = 0
    ) -> bool:
        """Set up a platform via config file or config entry.

        async_create_setup_task creates a coroutine that sets up platform.
        """
        logger = self.logger
        hass = self.hass
        full_name = f"{self.domain}.{self.platform_name}"

        logger.info("Setting up %s", full_name)
        warn_task = hass.loop.call_later(
            SLOW_SETUP_WARNING,
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

                # Block till all services are added
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
                    "Setup of platform %s is taking longer than %s seconds."
                    " Startup will proceed without waiting any longer.",
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

    @callback
    def _async_schedule_add_services(
        self, new_services: Iterable[PlatformService]
    ) -> None:
        """Schedule adding service for a single platform async."""
        task = self.hass.async_create_task(
            self.async_add_services(new_services),
        )

        if not self._setup_complete:
            self._tasks.append(task)

    async def async_add_services(self, new_services: Iterable[PlatformService]) -> None:
        """Add service for a single platform async."""
        if not new_services:
            return

        tasks = [self._async_add_service(service) for service in new_services]
        timeout = max(SLOW_ADD_SERVICE_MAX_WAIT * len(tasks), SLOW_ADD_MIN_TIMEOUT)

        try:
            async with self.hass.timeout.async_timeout(timeout, self.domain):
                await asyncio.gather(*tasks)
        except asyncio.TimeoutError:
            self.logger.warning(
                "Timed out adding service for domain %s with platform %s after %ds",
                self.domain,
                self.platform_name,
                timeout,
            )
        except Exception:
            self.logger.exception(
                "Error adding service for domain %s with platform %s",
                self.domain,
                self.platform_name,
            )
            raise

    async def _async_add_service(
        self,
        service: PlatformService,
    ) -> None:
        """Add a service to the platform."""
        service.add_to_platform_start(
            self.hass,
            self,
            self._get_parallel_updates_semaphore(service.is_async),
        )

        await self._async_register_service(service, service.service_schema)

        self.services[service.service_name] = service

        @callback
        def remove_service_cb() -> None:
            """Remove service from services list."""
            self.services.pop(service.service_name)

            domain_platform_services = [
                domain_service
                for platform in self.hass.data[DATA_SERVICE_PLATFORM][
                    self.platform_name
                ]
                for domain_service in platform.services
                if platform.domain == self.domain
                and domain_service == service.service_name
            ]

            # Only remove service from core
            # if this is the last domain platform service
            # for platform_name and service name.
            if len(domain_platform_services) >= 1:
                return

            self.hass.services.async_remove(self.domain, service.service_name)

        service.async_on_remove(remove_service_cb)

    @callback
    def async_destroy(self) -> None:
        """Remove all services and data."""
        if self not in self.hass.data[DATA_SERVICE_PLATFORM][self.platform_name]:
            raise ValueError(f"{self} was already destroyed")

        self.async_cancel_retry_setup()

        for service in list(self.services.values()):
            service.async_remove()

        self._setup_complete = False
        self.hass.data[DATA_SERVICE_PLATFORM][self.platform_name].remove(self)

    async def _async_register_service(
        self,
        service: PlatformService,
        schema: vol.Schema,
    ) -> None:
        """Register a platform service.

        Services will automatically be shared by all platforms of the same domain.
        """
        # We need to hold the lock since we yield to the loop
        # before we can finish registering the service.
        if self.domain not in self.hass.data[DATA_SERVICE_PLATFORM_LOCKS]:
            self.hass.data[DATA_SERVICE_PLATFORM_LOCKS][self.domain] = asyncio.Lock()

        async with self.hass.data[DATA_SERVICE_PLATFORM_LOCKS][self.domain]:
            if self.hass.services.has_service(self.domain, service.service_name):
                return

            # Setting the service description can raise errors
            # when getting the integration and loading the services.yaml.
            try:
                await self._set_service_description(service)
            except Exception:
                service.add_to_platform_abort()
                raise

        async def handle_service(call: ServiceCall) -> None:
            """Handle the service."""
            await integration_service_call(
                self.hass,
                [
                    plf
                    for plf in self.hass.data[DATA_SERVICE_PLATFORM][self.platform_name]
                    if plf.domain == self.domain
                ],
                call,
            )

        self.hass.services.async_register(
            self.domain, service.service_name, handle_service, schema
        )

    async def _set_service_description(self, service: PlatformService) -> None:
        """Set service description for a service and domain."""
        service_description = service.service_description
        integration = await async_get_integration(self.hass, service_description.domain)
        services_dict = cast(
            Dict[str, Dict[str, Any]],
            await self.hass.async_add_executor_job(
                load_services_file, self.hass, integration
            ),
        )
        if not services_dict:
            raise HomeAssistantError(f"Invalid services.yaml file for {self.domain}")

        # Register the service description
        service_desc = {
            CONF_NAME: services_dict[service_description.service_id][CONF_NAME],
            CONF_DESCRIPTION: services_dict[service_description.service_id][
                CONF_DESCRIPTION
            ],
            CONF_FIELDS: services_dict[service_description.service_id][CONF_FIELDS],
        }
        async_set_service_schema(
            self.hass, self.domain, service.service_name, service_desc
        )


@dataclass
class ServiceDescription:
    """Represent a service description."""

    domain: str
    service_id: str


@callback
def async_get_platforms(
    hass: HomeAssistant, integration_name: str
) -> list[ServicePlatform]:
    """Find existing platforms."""
    if (
        DATA_SERVICE_PLATFORM not in hass.data
        or integration_name not in hass.data[DATA_SERVICE_PLATFORM]
    ):
        return []

    platforms: list[ServicePlatform] = hass.data[DATA_SERVICE_PLATFORM][
        integration_name
    ]

    return platforms
