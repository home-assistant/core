"""Services for the Quotable integration."""

from functools import partial
from http import HTTPStatus
import logging
from typing import Any

import aiohttp
import bleach

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.json import JsonObjectType

from .const import (
    ATTR_AUTHOR,
    ATTR_CONTENT,
    ATTR_DATA,
    ATTR_ERROR,
    ATTR_NAME,
    ATTR_SELECTED_AUTHORS,
    ATTR_SELECTED_TAGS,
    ATTR_SLUG,
    ATTR_STYLES,
    ATTR_SUCCESS,
    ATTR_UPDATE_FREQUENCY,
    DOMAIN,
    ERROR_FETCHING_DATA_FROM_QUOTABLE_API,
    ERROR_MISSING_SEARCH_QUERY,
    ERROR_UNKNOWN,
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

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_UPDATE_CONFIGURATION,
        service_func=partial(_update_configuration_service, hass),
    )


async def _fetch_all_tags_service(
    session: aiohttp.ClientSession, service: ServiceCall
) -> ServiceResponse:
    try:
        response = await session.get(GET_TAGS_URL, timeout=HTTP_CLIENT_TIMEOUT)
        if response.status == HTTPStatus.OK:
            tags = await response.json()
            if tags:
                tags = [
                    {
                        ATTR_NAME: bleach.clean(tag[ATTR_NAME]),
                        ATTR_SLUG: bleach.clean(tag[ATTR_SLUG]),
                    }
                    for tag in tags
                ]
                return _success_response(tags)

    except aiohttp.ClientError as err:
        _LOGGER.error(
            "An error occurred while fetching all tags from the Quotable API. Details: %s",
            err,
        )
        return _error_response(ERROR_FETCHING_DATA_FROM_QUOTABLE_API)

    _LOGGER.error(ERROR_UNKNOWN)
    return _error_response(ERROR_UNKNOWN)


async def _fetch_all_authors_service(
    session: aiohttp.ClientSession, service: ServiceCall
) -> ServiceResponse:
    try:
        response = await session.get(GET_AUTHORS_URL, timeout=HTTP_CLIENT_TIMEOUT)
        if response.status == HTTPStatus.OK:
            json = await response.json()
            if results := json.get("results"):
                authors = [
                    {
                        ATTR_NAME: bleach.clean(result[ATTR_NAME]),
                        ATTR_SLUG: bleach.clean(result[ATTR_SLUG]),
                    }
                    for result in results
                ]
                return _success_response(authors)

    except aiohttp.ClientError as err:
        _LOGGER.error(
            "An error occurred while fetching all authors from the Quotable API. Details: %s",
            err,
        )
        return _error_response(ERROR_FETCHING_DATA_FROM_QUOTABLE_API)

    _LOGGER.error(ERROR_UNKNOWN)
    return _error_response(ERROR_UNKNOWN)


async def _search_authors_service(
    session: aiohttp.ClientSession, service: ServiceCall
) -> ServiceResponse:
    query = service.data.get("query")

    if not query:
        return _error_response(ERROR_MISSING_SEARCH_QUERY)

    params = {"query": query, "matchThreshold": 1}

    try:
        response = await session.get(
            SEARCH_AUTHORS_URL, params=params, timeout=HTTP_CLIENT_TIMEOUT
        )

        if response.status == HTTPStatus.OK:
            json = await response.json()
            if results := json.get("results"):
                authors = [
                    {
                        ATTR_NAME: bleach.clean(result[ATTR_NAME]),
                        ATTR_SLUG: bleach.clean(result[ATTR_SLUG]),
                    }
                    for result in results
                ]
                return _success_response(authors)

    except aiohttp.ClientError as err:
        _LOGGER.error(
            "An error occurred while searching authors from the Quotable API. Details: %s",
            err,
        )
        return _error_response(ERROR_FETCHING_DATA_FROM_QUOTABLE_API)

    _LOGGER.error(ERROR_UNKNOWN)
    return _error_response(ERROR_UNKNOWN)


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

    try:
        response = await session.get(
            FETCH_A_QUOTE_URL, params=params, timeout=HTTP_CLIENT_TIMEOUT
        )

        if response.status == HTTPStatus.OK:
            quotes = await response.json()
            if quotes:
                quote = {
                    ATTR_AUTHOR: bleach.clean(quotes[0][ATTR_AUTHOR]),
                    ATTR_CONTENT: bleach.clean(quotes[0][ATTR_CONTENT]),
                }

                hass.bus.async_fire(EVENT_NEW_QUOTE_FETCHED, quote)

                if service.return_response:
                    return _success_response(quote)

                return None

    except aiohttp.ClientError as err:
        _LOGGER.error(
            "An error occurred while fetching a quote from the Quotable API. Details: %s",
            err,
        )
        return _error_response(ERROR_FETCHING_DATA_FROM_QUOTABLE_API)

    _LOGGER.error(ERROR_UNKNOWN)
    return _error_response(ERROR_UNKNOWN)


async def _update_configuration_service(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    if quotable := hass.data.get(DOMAIN):
        quotable.update_configuration(
            service.data[ATTR_SELECTED_TAGS],
            service.data[ATTR_SELECTED_AUTHORS],
            service.data[ATTR_UPDATE_FREQUENCY],
            service.data[ATTR_STYLES],
        )


def _success_response(data: Any) -> JsonObjectType:
    return {
        ATTR_SUCCESS: True,
        ATTR_DATA: data,
    }


def _error_response(error: str) -> JsonObjectType:
    return {
        ATTR_SUCCESS: False,
        ATTR_ERROR: error,
    }
