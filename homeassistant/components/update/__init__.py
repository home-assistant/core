"""Support for Update."""
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

DOMAIN = "update"

INFO_CALLBACK_TIMEOUT = 5
STORAGE_VERSION = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Update integration."""
    store = storage.Store(
        hass=hass,
        version=STORAGE_VERSION,
        key=DOMAIN,
    )
    hass.data[DOMAIN] = UpdateData(
        store=store,
        skip=set(await store.async_load() or []),
    )

    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, handle_update)
    websocket_api.async_register_command(hass, handle_skip)

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_update_platform
    )

    return True


async def _register_update_platform(hass, integration_domain, platform) -> None:
    """Register a update platform."""
    if hasattr(platform, "async_register"):
        platform.async_register(UpdateRegistration(hass, integration_domain))


async def get_integration_info(
    hass: HomeAssistant,
    registration: UpdateRegistration,
) -> list[UpdateDescription] | None:
    """Get integration update details."""
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
    update_data: UpdateData,
    domain: str,
    identifier: str,
) -> UpdateDescription | None:
    """Get an update."""
    return next(
        (
            update
            for update in update_data.updates.get(domain, [])
            if update.identifier == identifier
        ),
        None,
    )


def _filtered_updates(update_data: UpdateData) -> list[dict]:
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
        }
        for domain, domain_data in update_data.updates.items()
        if domain_data is not None
        for description in domain_data
        if f"{domain}_{description.identifier}_{description.available_version}"
        not in update_data.skip
    ]


@websocket_api.websocket_command({vol.Required("type"): "update/info"})
@websocket_api.async_response
async def handle_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
):
    """Get pending updates from all platforms."""
    update_data: UpdateData = hass.data[DOMAIN]

    for domain, domain_data in zip(
        update_data.registrations,
        await asyncio.gather(
            *(
                get_integration_info(hass, registration)
                for registration in update_data.registrations.values()
            )
        ),
    ):
        update_data.updates[domain] = domain_data

    connection.send_result(msg["id"], _filtered_updates(update_data))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "update/skip",
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
    update_data: UpdateData = hass.data[DOMAIN]
    update_details = _get_update_details(update_data, msg["domain"], msg["identifier"])
    if update_details is not None:
        update_data.skip.add(
            f"{msg['domain']}_{update_details.identifier}_{update_details.available_version}"
        )
        update_data.updates[msg["domain"]].remove(update_details)
        await update_data.store.async_save(list(update_data.skip))

    connection.send_result(
        msg["id"],
        _filtered_updates(update_data),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "update/update",
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
    update_data: UpdateData = hass.data[DOMAIN]
    update_details = _get_update_details(update_data, msg["domain"], msg["identifier"])

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

    update_data.updates[msg["domain"]].remove(update_details)

    connection.send_result(
        msg["id"],
        _filtered_updates(update_data),
    )


@dataclasses.dataclass()
class UpdateData:
    """Data for the update integration."""

    store: storage.Store
    skip: set[str]
    registrations: dict[str, UpdateRegistration] = dataclasses.field(
        default_factory=dict
    )
    updates: dict[str, list[UpdateDescription]] = dataclasses.field(
        default_factory=dict
    )


@dataclasses.dataclass()
class UpdateDescription:
    """Describe an update update."""

    identifier: str
    name: str
    current_version: str
    available_version: str
    update_callback: Callable[[HomeAssistant, UpdateDescription], Awaitable[bool]]
    changelog_url: str | None = None
    icon_url: str | None = None


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
        update_data: UpdateData = self.hass.data[DOMAIN]
        self.updates_callback = updates_callback
        update_data.registrations[self.domain] = self
