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
    DOMAIN,
    GET_TAGS_URL,
    HTTP_CLIENT_TIMEOUT,
    SERVICE_FETCH_A_QUOTE,
    SERVICE_GET_TAGS,
    SERVICE_SEARCH_AUTHORS,
)

_LOGGER = logging.getLogger(__name__)


def register_services(hass: HomeAssistant) -> None:
    """Register services for the Quotable component."""

    session = async_get_clientsession(hass)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_GET_TAGS,
        service_func=partial(_get_tags_service, session),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH_AUTHORS, _search_authors_service
    )

    hass.services.async_register(DOMAIN, SERVICE_FETCH_A_QUOTE, _fetch_a_quote_service)


async def _get_tags_service(
    session: aiohttp.ClientSession, _: ServiceCall
) -> ServiceResponse:
    response = await session.get(GET_TAGS_URL, timeout=HTTP_CLIENT_TIMEOUT)
    if response.status == HTTPStatus.OK:
        data = await response.json()
        if data:
            tags = {item["slug"]: item["name"] for item in data}
            return tags

    return None


async def _search_authors_service(service: ServiceCall) -> None:
    pass


async def _fetch_a_quote_service(service: ServiceCall) -> None:
    pass
