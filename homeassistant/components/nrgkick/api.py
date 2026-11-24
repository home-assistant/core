"""API helpers for the NRGkick integration."""

from collections.abc import Awaitable

from nrgkick_api import (
    NRGkickAPIDisabledError,
    NRGkickAuthenticationError,
    NRGkickCommandRejectedError,
    NRGkickConnectionError,
    NRGkickHTTPError,
    NRGkickInvalidResponseError,
    NRGkickTimeoutError,
    NRGkickUnreachableError,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


async def async_api_call[_T](awaitable: Awaitable[_T]) -> _T:
    """Call the NRGkick API and map common library errors.

    This helper is intended for command-style calls from entities
    (switch/number/etc.), where errors should surface as user-facing
    `HomeAssistantError` exceptions. Regular polling is handled by the
    coordinator.
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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        ) from err
    except NRGkickAPIDisabledError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="json_api_disabled",
        ) from err
    except NRGkickInvalidResponseError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_response",
        ) from err
    except NRGkickTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout",
        ) from err
    except NRGkickUnreachableError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unreachable",
        ) from err
    except NRGkickHTTPError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="http_error",
            translation_placeholders={"status": str(err.status)},
        ) from err
    except NRGkickConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="communication_error",
        ) from err
