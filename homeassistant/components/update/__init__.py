"""Support for Update."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import dataclasses
import logging
from types import ModuleType
from typing import Any, Protocol

import async_timeout
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import integration_platform, storage
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "update"

INFO_CALLBACK_TIMEOUT = 5
STORAGE_VERSION = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Update integration."""
    hass.data[DOMAIN] = UpdateManager(hass=hass)

    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, perform_update)
    websocket_api.async_register_command(hass, handle_skip)

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_update_platform
    )

    return True


async def _register_update_platform(
    hass: HomeAssistant,
    integration_domain: str,
    platform: ModuleType,
) -> None:
    """Register an update platform."""
    if hasattr(platform, "async_register"):
        platform.async_register(UpdateRegistration(hass, integration_domain))


@websocket_api.websocket_command({vol.Required("type"): "update/info"})
@websocket_api.async_response
async def handle_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Get pending updates from all platforms."""
    manager: UpdateManager = hass.data[DOMAIN]
    updates = await manager.gather_updates()
    connection.send_result(msg["id"], updates)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "update/skip",
        vol.Required("domain"): str,
        vol.Required("identifier"): str,
    }
)
@callback
def handle_skip(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Skip an update."""
    manager: UpdateManager = hass.data[DOMAIN]
    manager.skip_update(msg["domain"], msg["identifier"])
    connection.send_result(msg["id"], manager.filtered_updates)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "update/update",
        vol.Required("domain"): str,
        vol.Required("identifier"): str,
        vol.Optional("backup"): bool,
    }
)
@websocket_api.async_response
async def perform_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle an update."""
    manager: UpdateManager = hass.data[DOMAIN]
    result = await manager.perform_update(
        msg["domain"], msg["identifier"], **{"backup": msg.get("backup")}
    )
    if result is None:
        connection.send_error(
            msg["id"],
            "not_found",
            f"No updates found for {msg['domain']} and {msg['identifier']}",
        )
        return

    if not result:
        connection.send_error(msg["id"], "update_failed", "Update failed")
        return

    connection.send_result(msg["id"], manager.filtered_updates)


class UpdateDescriptionUpdateCallback(Protocol):
    """Protocol type for UpdateDescription.update_callback."""

    def __call__(
        self,
        hass: HomeAssistant,
        description: UpdateDescription,
        **kwargs: Any,
    ) -> Coroutine[None, None, bool]:
        """Perform an update."""


@dataclasses.dataclass()
class UpdateDescription:
    """Describe an update update."""

    identifier: str
    name: str
    current_version: str
    available_version: str
    update_callback: UpdateDescriptionUpdateCallback
    changelog_content: str | None = None
    changelog_url: str | None = None
    icon_url: str | None = None
    provides_backup: bool = False


@dataclasses.dataclass()
class UpdateRegistration:
    """Helper class to track platform registration."""

    hass: HomeAssistant
    domain: str
    updates_callback: Callable[
        [HomeAssistant], Awaitable[list[UpdateDescription]]
    ] | None = None

    @callback
    def async_register(
        self,
        updates_callback: Callable[[HomeAssistant], Awaitable[list[UpdateDescription]]],
    ):
        """Register the updates info callback."""
        manager: UpdateManager = self.hass.data[DOMAIN]
        self.updates_callback = updates_callback
        manager.register(self)


class UpdateManager:
    """Update manager for the update integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the update manager."""
        self._hass = hass
        self._store = storage.Store(
            hass=hass,
            version=STORAGE_VERSION,
            key=DOMAIN,
        )
        self._skip: set[str] = set()
        self._updating: set[str] = set()
        self._registrations: dict[str, UpdateRegistration] = {}
        self._updates: dict[str, list[UpdateDescription]] = {}
        self._loaded = False

    @property
    def filtered_updates(self) -> list[dict]:
        """Return a list of updates that are not skipped."""
        return [
            {
                "domain": domain,
                "identifier": description.identifier,
                "name": description.name,
                "current_version": description.current_version,
                "available_version": description.available_version,
                "changelog_url": description.changelog_url,
                "icon_url": description.icon_url,
                "provides_backup": description.provides_backup,
            }
            for domain, domain_data in self._updates.items()
            if domain_data is not None
            for description in domain_data
            if f"{domain}_{description.identifier}_{description.available_version}"
            not in self._skip
        ]

    async def gather_updates(self) -> list[dict]:
        """Gather updates."""
        if not self._loaded:
            self._skip = set(await self._store.async_load() or [])
            self._loaded = True

        for domain, domain_data in zip(
            self._registrations,
            await asyncio.gather(
                *(
                    self._get_integration_info(registration)
                    for registration in self._registrations.values()
                )
            ),
        ):
            self._updates[domain] = domain_data
        return self.filtered_updates

    @callback
    def _data_to_save(self) -> list:
        """Schedule storing the data."""
        return list(self._skip)

    def _get_update_description(
        self, domain: str, identifier: str
    ) -> UpdateDescription | None:
        """Get an update."""
        return next(
            (
                update
                for update in self._updates.get(domain, [])
                if update.identifier == identifier
            ),
            None,
        )

    def register(self, registration: UpdateRegistration) -> None:
        """Register an update handler."""
        self._registrations[registration.domain] = registration

    async def perform_update(
        self,
        domain: str,
        identifier: str,
        **kwargs: Any,
    ) -> bool | None:
        """Perform an update."""
        update_description = self._get_update_description(domain, identifier)

        if update_description is None:
            return None

        self._updating.add(f"{domain}_{identifier}")
        if not await update_description.update_callback(
            self._hass,
            update_description,
            **kwargs,
        ):
            return False

        self._updates[domain].remove(update_description)
        self._updating.remove(f"{domain}_{identifier}")
        return True

    @callback
    def skip_update(self, domain: str, identifier: str) -> None:
        """Skip an update."""
        update_description = self._get_update_description(domain, identifier)
        if update_description is None:
            return

        self._skip.add(
            f"{domain}_{update_description.identifier}_{update_description.available_version}"
        )
        self._updates[domain].remove(update_description)
        self._store.async_delay_save(self._data_to_save, 60)

    async def _get_integration_info(
        self,
        registration: UpdateRegistration,
    ) -> list[UpdateDescription] | None:
        """Get integration update details."""
        assert registration.updates_callback

        try:
            async with async_timeout.timeout(INFO_CALLBACK_TIMEOUT):
                return await registration.updates_callback(self._hass)
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout while getting updates from %s", registration.domain
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error fetching info from %s", registration.domain)
        return None
