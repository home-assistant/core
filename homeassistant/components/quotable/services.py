"""Services for the Quotable integration."""

from functools import partial
from http import HTTPStatus
import logging

import aiohttp
import bleach

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
    ATTR_STYLES,
    ATTR_UPDATE_FREQUENCY,
    DOMAIN,
    EVENT_NEW_QUOTE_FETCHED,
    FETCH_A_QUOTE_URL,
    GET_AUTHORS_URL,
    GET_TAGS_URL,
    HTTP_CLIENT_TIMEOUT,
    SEARCH_AUTHORS_URL,
    SERVICE_FETCH_A_QUOTE,
    SERVICE_FETCH_ALL_AUTHORS,
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
        service=SERVICE_FETCH_ALL_AUTHORS,
        service_func=partial(_fetch_all_authors_service, session),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SEARCH_AUTHORS,
        service_func=partial(_search_authors_service, session),
        supports_response=SupportsResponse.ONLY,
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
        tags = await response.json()
        if tags:
            tags = {
                bleach.clean(tag.get("slug")): bleach.clean(tag.get("name"))
                for tag in tags
            }
            return tags

    return None


async def _fetch_all_authors_service(
    session: aiohttp.ClientSession, service: ServiceCall
) -> ServiceResponse:
    response = await session.get(GET_AUTHORS_URL, timeout=HTTP_CLIENT_TIMEOUT)
    if response.status == HTTPStatus.OK:
        data = await response.json()
        if authorslist := data.get("results"):
            authorslist = {
                bleach.clean(author.get("slug")): bleach.clean(author.get("name"))
                for author in authorslist
            }
            return authorslist

    return None


async def _search_authors_service(
    session: aiohttp.ClientSession, service: ServiceCall
) -> ServiceResponse:
    query = service.data.get("query")

    if not query:
        return None

    params = {"query": query, "matchThreshold": 1}

    response = await session.get(
        SEARCH_AUTHORS_URL, params=params, timeout=HTTP_CLIENT_TIMEOUT
    )

    if response.status == HTTPStatus.OK:
        data = await response.json()
        if authors := data.get("results"):
            return {
                bleach.clean(author.get("slug")): bleach.clean(author.get("name"))
                for author in authors
            }

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
        quotes = await response.json()
        if quotes:
            quote = {
                "author": bleach.clean(quotes[0].get("author")),
                "content": bleach.clean(quotes[0].get("content")),
            }

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
            service.data[ATTR_STYLES],
        )
