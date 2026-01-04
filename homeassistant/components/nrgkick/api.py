"""NRGkick API client wrapper for Home Assistant.

This module provides a thin wrapper around the nrgkick-api library,
adding Home Assistant-specific exception handling with translation support.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
import logging
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar, cast

import aiohttp
from nrgkick_api import (
    NRGkickAPI as LibraryAPI,
    NRGkickAPIDisabledError,
    NRGkickAuthenticationError,
    NRGkickConnectionError,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")


def _wrap_api_errors(
    func: Callable[Concatenate[NRGkickAPI, _P], Awaitable[_R]],
) -> Callable[Concatenate[NRGkickAPI, _P], Awaitable[_R]]:
    """Wrap API calls with Home Assistant exception translation."""

    @wraps(func)
    async def wrapper(self: NRGkickAPI, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except NRGkickAuthenticationError as err:
            _LOGGER.warning(
                "Authentication failed for NRGkick device at %s: %s",
                self.host,
                err,
            )
            raise NRGkickApiClientAuthenticationError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
                translation_placeholders={"host": self.host},
            ) from err
        except NRGkickAPIDisabledError as err:
            _LOGGER.info(
                "JSON API is disabled for NRGkick device at %s",
                self.host,
            )
            raise NRGkickApiClientApiDisabledError(
                translation_domain=DOMAIN,
                translation_key="json_api_disabled",
                translation_placeholders={"host": self.host},
            ) from err
        except NRGkickConnectionError as err:
            _LOGGER.error(
                "Communication error with NRGkick device at %s: %s",
                self.host,
                err,
            )
            raise NRGkickApiClientCommunicationError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except (TimeoutError, aiohttp.ClientError, OSError) as err:
            _LOGGER.error(
                "Unexpected communication error with NRGkick device at %s: %s",
                self.host,
                err,
            )
            raise NRGkickApiClientCommunicationError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

    return (
        cast(Callable[Concatenate[NRGkickAPI, _P], Awaitable[_R]], wrapper)
        if TYPE_CHECKING
        else wrapper
    )


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


class NRGkickAPI:
    """Home Assistant wrapper for NRGkick API client.

    This class wraps the standalone nrgkick-api library and provides
    exception translation for Home Assistant compatibility.
    """

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client wrapper.

        Args:
            host: IP address or hostname of the NRGkick device.
            username: Optional username for Basic Auth.
            password: Optional password for Basic Auth.
            session: aiohttp ClientSession for requests.

        """
        self.host = host
        self._api = LibraryAPI(
            host=host,
            username=username,
            password=password,
            session=session,
        )

    @_wrap_api_errors
    async def get_info(
        self,
        sections: list[str] | None = None,
        *,
        raw: bool = True,
    ) -> dict[str, Any]:
        """Get device information.

        Args:
            sections: Optional list of sections to retrieve.
            raw: If True, return raw numeric values for enum fields.
                This enables proper translation via Home Assistant's
                translation system.

        Returns:
            Device information dictionary.

        """
        return await self._api.get_info(sections, raw=raw)

    @_wrap_api_errors
    async def get_control(self) -> dict[str, Any]:
        """Get current control parameters.

        Returns:
            Control parameters dictionary.

        """
        return await self._api.get_control()

    @_wrap_api_errors
    async def get_values(
        self,
        sections: list[str] | None = None,
        *,
        raw: bool = True,
    ) -> dict[str, Any]:
        """Get current values.

        Args:
            sections: Optional list of sections to retrieve.
            raw: If True, return raw numeric values for enum fields.
                This enables proper translation via Home Assistant's
                translation system.

        Returns:
            Current values dictionary.

        """
        return await self._api.get_values(sections, raw=raw)

    @_wrap_api_errors
    async def set_current(self, current: float) -> dict[str, Any]:
        """Set charging current.

        Args:
            current: Charging current in Amps (6.0-32.0).

        Returns:
            Response dictionary with confirmed value.

        """
        return await self._api.set_current(current)

    @_wrap_api_errors
    async def set_charge_pause(self, pause: bool) -> dict[str, Any]:
        """Set charge pause state.

        Args:
            pause: True to pause charging, False to resume.

        Returns:
            Response dictionary with confirmed value.

        """
        return await self._api.set_charge_pause(pause)

    @_wrap_api_errors
    async def set_energy_limit(self, limit: int) -> dict[str, Any]:
        """Set energy limit in Wh (0 = no limit).

        Args:
            limit: Energy limit in Watt-hours.

        Returns:
            Response dictionary with confirmed value.

        """
        return await self._api.set_energy_limit(limit)

    @_wrap_api_errors
    async def set_phase_count(self, phases: int) -> dict[str, Any]:
        """Set phase count (1-3).

        Args:
            phases: Number of phases to use (1, 2, or 3).

        Returns:
            Response dictionary with confirmed value.

        """
        return await self._api.set_phase_count(phases)

    @_wrap_api_errors
    async def test_connection(self) -> bool:
        """Test if we can connect to the device.

        Returns:
            True if connection successful.

        """
        return await self._api.test_connection()
