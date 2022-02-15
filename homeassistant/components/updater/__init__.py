"""Support for Updater."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import dataclasses
import logging

import async_timeout
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import integration_platform, storage
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "updater"

INFO_CALLBACK_TIMEOUT = 5
STORAGE_VERSION = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Updater integration."""
    store = storage.Store(
        hass=hass,
        version=STORAGE_VERSION,
        key=DOMAIN,
    )
    hass.data[DOMAIN] = UpdaterData(
        store=store,
        skip=set(await store.async_load() or []),
    )

    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, handle_update)
    websocket_api.async_register_command(hass, handle_skip)

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_updater_platform
    )

    return True


async def _register_updater_platform(hass, integration_domain, platform) -> None:
    """Register a updater platform."""
    if hasattr(platform, "async_register_updater"):
        platform.async_register_updater(UpdaterRegistration(hass, integration_domain))


async def get_integration_info(
    hass: HomeAssistant,
    registration: UpdaterRegistration,
) -> list[UpdateDescription] | None:
    """Get integration updater details."""
    assert registration.updates_callback

    try:
        async with async_timeout.timeout(INFO_CALLBACK_TIMEOUT):
            return await registration.updates_callback(hass)
    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout while getting updates from %s", registration.domain)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error fetching info")
    return None


def _get_update_details(
    hass: HomeAssistant,
    domain: str,
    identifier: str,
) -> UpdateDescription | None:
    """Get an update."""
    updater_data: UpdaterData = hass.data[DOMAIN]
    return next(
        (
            update
            for update in updater_data.updates.get(domain, [])
            if update.identifier == identifier
        ),
        None,
    )


def _filtered_updates(updater_data: UpdaterData) -> list[dict]:
    """Return a list of updates that are not skipped."""
    return [
        {
            "domain": domain,
            "identifier": update_data.identifier,
            "name": update_data.name,
            "current_version": update_data.current_version,
            "available_version": update_data.available_version,
            "changelog_url": update_data.changelog_url,
            "icon_url": update_data.icon_url,
        }
        for domain, domain_data in updater_data.updates.items()
        if domain_data is not None
        for update_data in domain_data
        if f"{domain}_{update_data.identifier}_{update_data.available_version}"
        not in updater_data.skip
    ]


@websocket_api.websocket_command({vol.Required("type"): "updater/info"})
@websocket_api.async_response
async def handle_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
):
    """Get pending updates from all platforms."""
    updater_data: UpdaterData = hass.data[DOMAIN]

    for domain, domain_data in zip(
        updater_data.registrations,
        await asyncio.gather(
            *(
                get_integration_info(hass, registration)
                for registration in updater_data.registrations.values()
            )
        ),
    ):
        updater_data.updates[domain] = domain_data

    connection.send_result(msg["id"], _filtered_updates(updater_data))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "updater/skip",
        vol.Required("domain"): str,
        vol.Required("identifier"): str,
    }
)
@websocket_api.async_response
async def handle_skip(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
):
    """Skip an update."""
    updater_data: UpdaterData = hass.data[DOMAIN]
    update_details = _get_update_details(hass, msg["domain"], msg["identifier"])
    if update_details is not None:
        updater_data.skip.add(
            f"{msg['domain']}_{update_details.identifier}_{update_details.available_version}"
        )
        updater_data.updates[msg["domain"]].remove(update_details)
        await updater_data.store.async_save(list(updater_data.skip))

    connection.send_result(
        msg["id"],
        _filtered_updates(updater_data),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "updater/update",
        vol.Required("domain"): str,
        vol.Required("identifier"): str,
    }
)
@websocket_api.async_response
async def handle_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
):
    """Handle an update."""
    updater_data: UpdaterData = hass.data[DOMAIN]
    update_details = _get_update_details(hass, msg["domain"], msg["identifier"])

    if update_details is None:
        connection.send_error(
            msg["id"],
            "not_found",
            f"No updates found for {msg['domain']} and {msg['identifier']}",
        )
        return

    if not await update_details.update_callback(hass, update_details):
        connection.send_error(msg["id"], "update_failed", "Update failed")
        return

    updater_data.updates[msg["domain"]].remove(update_details)

    connection.send_result(
        msg["id"],
        _filtered_updates(updater_data),
    )


@dataclasses.dataclass()
class UpdaterData:
    """Data for the updater integration."""

    store: storage.Store
    skip: set[str]
    registrations: dict[str, UpdaterRegistration] = dataclasses.field(
        default_factory=dict
    )
    updates: dict[str, list[UpdateDescription]] = dataclasses.field(
        default_factory=dict
    )


@dataclasses.dataclass()
class UpdateDescription:
    """Describe an updater update."""

    identifier: str
    name: str
    current_version: str
    available_version: str
    update_callback: Callable[[HomeAssistant, UpdateDescription], Awaitable[bool]]
    changelog_url: str | None = None
    icon_url: str | None = None


@dataclasses.dataclass()
class UpdaterRegistration:
    """Helper class to track platform registration."""

    hass: HomeAssistant
    domain: str
    updates_callback: Callable[
        [HomeAssistant], Awaitable[list[UpdateDescription]]
    ] | None = None

    @callback
    def async_register_updater(
        self,
        updates_callback: Callable[[HomeAssistant], Awaitable[list[UpdateDescription]]],
    ):
        """Register the updates info callback."""
        updater_data: UpdaterData = self.hass.data[DOMAIN]
        self.updates_callback = updates_callback
        updater_data.registrations[self.domain] = self
