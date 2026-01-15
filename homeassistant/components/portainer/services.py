"""Services for the Portainer integration."""

from datetime import timedelta
import logging

from pyportainer import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN, ENDPOINT_ID
from .coordinator import PortainerConfigEntry

_LOGGER = logging.getLogger(__name__)

ATTR_DATE_UNTIL = "until"
ATTR_DANGLING = "dangling"

SERVICE_PRUNE_IMAGES = "prune_images"
SERVICE_PRUNE_IMAGES_SCHEMA = vol.Schema(
    {
        vol.Required(
            ENDPOINT_ID
        ): cv.positive_int,  # Expand this with a list of known edpoint IDs
        vol.Optional(ATTR_DATE_UNTIL): vol.All(
            cv.time_period, vol.Range(min=timedelta(minutes=1))
        ),
        vol.Optional(ATTR_DANGLING): cv.boolean,
    },
)


async def _extract_config_entry(service_call: ServiceCall) -> PortainerConfigEntry:
    """Extract config entry from the service call."""
    target_entry_ids = await async_extract_config_entry_ids(service_call)
    target_entries: list[PortainerConfigEntry] = [
        loaded_entry
        for loaded_entry in service_call.hass.config_entries.async_loaded_entries(
            DOMAIN
        )
        if loaded_entry.entry_id in target_entry_ids
    ]
    if not target_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )
    return target_entries[0]


async def prune_images(call: ServiceCall) -> None:
    """Prune unused images in Portainer, with more controls."""
    _LOGGER.debug("Set program call: %s", call)
    config_entry = await _extract_config_entry(call)
    coordinator = config_entry.runtime_data

    dangling = call.data.get(ATTR_DANGLING, False)
    try:
        await coordinator.portainer.images_prune(
            endpoint_id=call.data[ENDPOINT_ID],
            until=call.data.get(ATTR_DATE_UNTIL),
            dangling=dangling,
        )
    except PortainerAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"error": repr(err)},
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": repr(err)},
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
            translation_placeholders={"error": repr(err)},
        ) from err


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_PRUNE_IMAGES,
        prune_images,
        SERVICE_PRUNE_IMAGES_SCHEMA,
    )
