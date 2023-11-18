"""Services for the Quotable integration."""

from functools import partial
from http import HTTPStatus
import logging

import aiohttp

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_SELECTED_AUTHORS,
    ATTR_SELECTED_TAGS,
    ATTR_UPDATE_FREQUENCY,
    DOMAIN,
    EVENT_NEW_QUOTE_FETCHED,
    FETCH_A_QUOTE_URL,
    GET_TAGS_URL,
    HTTP_CLIENT_TIMEOUT,
    SEARCH_AUTHORS_URL,
    SERVICE_FETCH_A_QUOTE,
    SERVICE_FETCH_ALL_TAGS,
    SERVICE_SEARCH_AUTHORS,
    SERVICE_UPDATE_CONFIGURATION,
)

_LOGGER = logging.getLogger(__name__)


def register_services(hass: HomeAssistant) -> None:
    """Register services for the Quotable component."""

    session = async_get_clientsession(hass)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_FETCH_ALL_TAGS,
        service_func=partial(_fetch_all_tags_service, session),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SEARCH_AUTHORS,
        service_func=partial(_search_authors_service, session),
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_FETCH_A_QUOTE,
        service_func=partial(_fetch_a_quote_service, session, hass),
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.register(
        domain=DOMAIN,
        service=SERVICE_UPDATE_CONFIGURATION,
        service_func=partial(_update_configuration_service, hass),
    )


async def _fetch_all_tags_service(
    session: aiohttp.ClientSession, service: ServiceCall
) -> ServiceResponse:
    response = await session.get(GET_TAGS_URL, timeout=HTTP_CLIENT_TIMEOUT)
    if response.status == HTTPStatus.OK:
        data = await response.json()
        if data:
            tags = {item["slug"]: item["name"] for item in data}
            return tags

    return None


async def _search_authors_service(
    session: aiohttp.ClientSession, service: ServiceCall
) -> ServiceResponse:
    search_query = service.data.get("query")

    if not search_query:
        return None

    search_url = f"{SEARCH_AUTHORS_URL}?query={search_query}&matchThreshold=1"
    response = await session.get(search_url, timeout=HTTP_CLIENT_TIMEOUT)

    if response.status == HTTPStatus.OK:
        data = await response.json()
        if data and data.get("count", 0) > 0:
            authors = {item["slug"]: item["name"] for item in data["results"]}
            return authors

    return None


async def _fetch_a_quote_service(
    session: aiohttp.ClientSession, hass: HomeAssistant, service: ServiceCall
) -> ServiceResponse:
    """Get the Quotable instance from hass.data."""
    quotable = hass.data.get(DOMAIN)
    if quotable is None:
        return None

    params = {
        "tags": "|".join(quotable.config.get(ATTR_SELECTED_TAGS, [])),
        "author": "|".join(quotable.config.get(ATTR_SELECTED_AUTHORS, [])),
    }

    response = await session.get(
        FETCH_A_QUOTE_URL, params=params, timeout=HTTP_CLIENT_TIMEOUT
    )

    if response.status == HTTPStatus.OK:
        data = await response.json()
        if data:
            quote = {"author": data[0]["author"], "content": data[0]["content"]}

            hass.bus.fire(EVENT_NEW_QUOTE_FETCHED, quote)

            if service.return_response:
                return quote

    return None


def _update_configuration_service(hass: HomeAssistant, service: ServiceCall) -> None:
    if quotable := hass.data.get(DOMAIN):
        quotable.update_configuration(
            service.data[ATTR_SELECTED_TAGS],
            service.data[ATTR_SELECTED_AUTHORS],
            service.data[ATTR_UPDATE_FREQUENCY],
        )
