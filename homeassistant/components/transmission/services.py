"""Define services for the Transmission integration."""

from functools import partial
import logging
from typing import cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    ATTR_DELETE_DATA,
    ATTR_DOWNLOAD_PATH,
    ATTR_TORRENT,
    CONF_ENTRY_ID,
    DEFAULT_DELETE_DATA,
    DOMAIN,
    SERVICE_ADD_TORRENT,
    SERVICE_REMOVE_TORRENT,
    SERVICE_START_TORRENT,
    SERVICE_STOP_TORRENT,
)
from .coordinator import TransmissionDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTRY_ID): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)

SERVICE_ADD_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend(
        {
            vol.Required(ATTR_TORRENT): cv.string,
            vol.Optional(ATTR_DOWNLOAD_PATH): cv.string,
        }
    ),
)

SERVICE_REMOVE_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ID): cv.positive_int,
            vol.Optional(ATTR_DELETE_DATA, default=DEFAULT_DELETE_DATA): cv.boolean,
        }
    )
)

SERVICE_START_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend({vol.Required(CONF_ID): cv.positive_int}),
)

SERVICE_STOP_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ID): cv.positive_int,
        }
    )
)


def _get_coordinator_from_service_data(
    call: ServiceCall,
) -> TransmissionDataUpdateCoordinator:
    """Return coordinator for entry id."""
    config_entry_id: str = call.data[CONF_ENTRY_ID]
    if not (entry := call.hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": DOMAIN},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": entry.title},
        )
    return cast(TransmissionDataUpdateCoordinator, entry.runtime_data)


async def _async_add_torrent(service: ServiceCall) -> None:
    """Add new torrent to download."""
    coordinator = _get_coordinator_from_service_data(service)
    torrent: str = service.data[ATTR_TORRENT]
    download_path: str | None = service.data.get(ATTR_DOWNLOAD_PATH)

    if not (
        torrent.startswith(("http", "ftp:", "magnet:"))
        or service.hass.config.is_allowed_path(torrent)
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="could_not_add_torrent",
        )

    if download_path:
        await service.hass.async_add_executor_job(
            partial(coordinator.api.add_torrent, torrent, download_dir=download_path)
        )
    else:
        await service.hass.async_add_executor_job(coordinator.api.add_torrent, torrent)
    await coordinator.async_request_refresh()


async def _async_start_torrent(service: ServiceCall) -> None:
    """Start torrent."""
    coordinator = _get_coordinator_from_service_data(service)
    torrent_id = service.data[CONF_ID]
    await service.hass.async_add_executor_job(coordinator.api.start_torrent, torrent_id)
    await coordinator.async_request_refresh()


async def _async_stop_torrent(service: ServiceCall) -> None:
    """Stop torrent."""
    coordinator = _get_coordinator_from_service_data(service)
    torrent_id = service.data[CONF_ID]
    await service.hass.async_add_executor_job(coordinator.api.stop_torrent, torrent_id)
    await coordinator.async_request_refresh()


async def _async_remove_torrent(service: ServiceCall) -> None:
    """Remove torrent."""
    coordinator = _get_coordinator_from_service_data(service)
    torrent_id = service.data[CONF_ID]
    delete_data = service.data[ATTR_DELETE_DATA]
    await service.hass.async_add_executor_job(
        partial(coordinator.api.remove_torrent, torrent_id, delete_data=delete_data)
    )
    await coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Transmission integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_TORRENT,
        _async_add_torrent,
        schema=SERVICE_ADD_TORRENT_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_TORRENT,
        _async_remove_torrent,
        schema=SERVICE_REMOVE_TORRENT_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_TORRENT,
        _async_start_torrent,
        schema=SERVICE_START_TORRENT_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_TORRENT,
        _async_stop_torrent,
        schema=SERVICE_STOP_TORRENT_SCHEMA,
    )
