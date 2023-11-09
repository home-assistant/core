"""Services for the Quotable integration."""

# Use this HTTP library to make calls to the Quotable API

from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    DOMAIN,
    SERVICE_FETCH_A_QUOTE,
    SERVICE_GET_TAGS,
    SERVICE_SEARCH_AUTHORS,
)


def register_services(hass: HomeAssistant) -> None:
    """Register services for the Quotable component."""

    hass.services.register(DOMAIN, SERVICE_GET_TAGS, _get_tags_service)

    hass.services.register(DOMAIN, SERVICE_SEARCH_AUTHORS, _search_authors_service)

    hass.services.register(DOMAIN, SERVICE_FETCH_A_QUOTE, _fetch_a_quote_service)


def _get_tags_service(service: ServiceCall) -> None:
    pass


def _search_authors_service(service: ServiceCall) -> None:
    pass


def _fetch_a_quote_service(service: ServiceCall) -> None:
    pass
