"""Define services for the Feedreader integration."""

from typing import cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util.json import JsonValueType

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN
from .coordinator import FeedReaderConfigEntry

SERVICE_GET_POSTS = "get_posts"
SERVICE_GET_POSTS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
    }
)


def _async_get_entry(
    hass: HomeAssistant, config_entry_id: str
) -> FeedReaderConfigEntry:
    """Get the Feedreader config entry."""
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
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
    return cast(FeedReaderConfigEntry, entry)


async def _async_get_posts(call: ServiceCall) -> ServiceResponse:
    """Get requests made to Feedreader."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])

    return {"posts": cast(list[JsonValueType], entry.runtime_data.data)}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Feedreader integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_POSTS,
        _async_get_posts,
        schema=SERVICE_GET_POSTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
