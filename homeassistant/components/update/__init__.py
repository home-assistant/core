"""Support for Update."""
from __future__ import annotations

import asyncio
import dataclasses
import logging
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
    websocket_api.async_register_command(hass, handle_update)
    websocket_api.async_register_command(hass, handle_skip)

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_update_platform
    )

    return True


async def _register_update_platform(
    hass: HomeAssistant,
    integration_domain: str,
    platform: UpdatePlatformProtocol,
) -> None:
    """Register a update platform."""
    manager: UpdateManager = hass.data[DOMAIN]
    manager.add_platform(integration_domain, platform)


@websocket_api.websocket_command({vol.Required("type"): "update/info"})
@websocket_api.async_response
async def handle_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
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
        vol.Required("version"): str,
    }
)
@callback
def handle_skip(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Skip an update."""
    manager: UpdateManager = hass.data[DOMAIN]

    if not manager.domain_is_valid(msg["domain"]):
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Domain not supported"
        )
        return

    manager.skip_update(msg["domain"], msg["identifier"], msg["version"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "update/update",
        vol.Required("domain"): str,
        vol.Required("identifier"): str,
        vol.Required("version"): str,
        vol.Optional("backup"): bool,
    }
)
@websocket_api.async_response
async def handle_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle an update."""
    manager: UpdateManager = hass.data[DOMAIN]

    if not manager.domain_is_valid(msg["domain"]):
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Domain not supported"
        )
        return

    if not await manager.perform_update(
        domain=msg["domain"],
        identifier=msg["identifier"],
        version=msg["version"],
        backup=msg.get("backup"),
    ):
        connection.send_error(msg["id"], "update_failed", "Update failed")
        return

    connection.send_result(msg["id"])


class UpdatePlatformProtocol(Protocol):
    """Define the format that update platforms can have."""

    async def async_list_updates(self, hass: HomeAssistant) -> list[UpdateDescription]:
        """List all updates available in the integration."""

    async def async_perform_update(
        self,
        hass: HomeAssistant,
        identifier: str,
        version: str,
        **kwargs: Any,
    ) -> bool:
        """Perform an update."""


@dataclasses.dataclass()
class UpdateDescription:
    """Describe an update update."""

    identifier: str
    name: str
    current_version: str
    available_version: str
    changelog_content: str | None = None
    changelog_url: str | None = None
    icon_url: str | None = None
    provides_backup: bool = False


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
        self._platforms: dict[str, UpdatePlatformProtocol] = {}
        self._loaded = False

    def add_platform(
        self,
        integration_domain: str,
        platform: UpdatePlatformProtocol,
    ) -> None:
        """Add a platform to the update manager."""
        self._platforms[integration_domain] = platform

    async def gather_updates(self) -> list[dict[str, Any]]:
        """Gather updates."""
        if not self._loaded:
            self._skip = set(await self._store.async_load() or [])
            self._loaded = True

        updates: dict[str, list[UpdateDescription] | None] = {}

        for domain, update_descriptions in zip(
            self._platforms,
            await asyncio.gather(
                *(
                    self._get_integration_info(integration_domain, registration)
                    for integration_domain, registration in self._platforms.items()
                )
            ),
        ):
            updates[domain] = update_descriptions

        return [
            {
                "domain": integration_domain,
                **dataclasses.asdict(description),
            }
            for integration_domain, update_descriptions in updates.items()
            if update_descriptions is not None
            for description in update_descriptions
            if f"{integration_domain}_{description.identifier}_{description.available_version}"
            not in self._skip
        ]

    def domain_is_valid(self, domain: str) -> bool:
        """Return if the domain is valid."""
        return domain in self._platforms

    @callback
    def _data_to_save(self) -> list[str]:
        """Schedule storing the data."""
        return list(self._skip)

    async def perform_update(
        self,
        domain: str,
        identifier: str,
        version: str,
        **kwargs: Any,
    ) -> bool:
        """Perform an update."""
        return await self._platforms[domain].async_perform_update(
            hass=self._hass,
            identifier=identifier,
            version=version,
            **kwargs,
        )

    @callback
    def skip_update(self, domain: str, identifier: str, version: str) -> None:
        """Skip an update."""
        self._skip.add(f"{domain}_{identifier}_{version}")
        self._store.async_delay_save(self._data_to_save, 60)

    async def _get_integration_info(
        self,
        integration_domain: str,
        platform: UpdatePlatformProtocol,
    ) -> list[UpdateDescription] | None:
        """Get integration update details."""

        try:
            async with async_timeout.timeout(INFO_CALLBACK_TIMEOUT):
                return await platform.async_list_updates(hass=self._hass)
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout while getting updates from %s", integration_domain)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error fetching info from %s", integration_domain)
        return None
