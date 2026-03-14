"""API helpers and Home Assistant exceptions for the NRGkick integration."""

from __future__ import annotations

from collections.abc import Awaitable

import aiohttp
from nrgkick_api import (
    NRGkickAPIDisabledError,
    NRGkickAuthenticationError,
    NRGkickCommandRejectedError,
    NRGkickConnectionError,
    NRGkickInvalidResponseError,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


class NRGkickApiClientError(HomeAssistantError):
    """Base exception for NRGkick API client errors."""

    translation_domain = DOMAIN
    translation_key = "unknown_error"


class NRGkickApiClientCommunicationError(NRGkickApiClientError):
    """Exception for NRGkick API client communication errors."""

    translation_domain = DOMAIN
    translation_key = "communication_error"


class NRGkickApiClientAuthenticationError(NRGkickApiClientError):
    """Exception for NRGkick API client authentication errors."""

    translation_domain = DOMAIN
    translation_key = "authentication_error"


class NRGkickApiClientApiDisabledError(NRGkickApiClientError):
    """Exception for disabled NRGkick JSON API."""

    translation_domain = DOMAIN
    translation_key = "json_api_disabled"


class NRGkickApiClientInvalidResponseError(NRGkickApiClientError):
    """Exception for invalid responses from the device."""

    translation_domain = DOMAIN
    translation_key = "invalid_response"


async def async_api_call[_T](awaitable: Awaitable[_T]) -> _T:
    """Call the NRGkick API and map common library errors.

    This helper is intended for one-off API calls outside the coordinator,
    such as command-style calls (switch/number/etc.) and config flow
    validation, where errors should surface as user-facing `HomeAssistantError`
    exceptions. Regular polling is handled by the coordinator.
    """
    try:
        return await awaitable
    except NRGkickCommandRejectedError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_rejected",
            translation_placeholders={"reason": err.reason},
        ) from err
    except NRGkickAuthenticationError as err:
        raise NRGkickApiClientAuthenticationError from err
    except NRGkickAPIDisabledError as err:
        raise NRGkickApiClientApiDisabledError from err
    except NRGkickInvalidResponseError as err:
        raise NRGkickApiClientInvalidResponseError from err
    except NRGkickConnectionError as err:
        raise NRGkickApiClientCommunicationError(
            translation_placeholders={"error": str(err)}
        ) from err
    except (TimeoutError, aiohttp.ClientError, OSError) as err:
        raise NRGkickApiClientCommunicationError(
            translation_placeholders={"error": str(err)}
        ) from err
