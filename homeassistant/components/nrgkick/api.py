"""NRGkick API client wrapper for Home Assistant.

This module provides a thin wrapper around the nrgkick-api library,
adding Home Assistant-specific exception handling with translation support.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar, cast

import aiohttp

# pylint: disable=import-error
from nrgkick_api import (
    NRGkickAPI as LibraryAPI,
    NRGkickAuthenticationError,
    NRGkickConnectionError,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

# pylint: enable=import-error


_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")


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

    async def _wrap_call(
        self,
        coro: Any,
        return_type: type[_T],  # pylint: disable=unused-argument
    ) -> _T:
        """Wrap library calls with Home Assistant exception translation.

        Args:
            coro: Coroutine from the library API.
            return_type: Expected return type for type safety (used by mypy).

        Returns:
            Result from the library call, cast to expected type.

        Raises:
            NRGkickApiClientAuthenticationError: If authentication fails.
            NRGkickApiClientCommunicationError: If communication fails.

        """
        try:
            result = await coro
            return cast(_T, result)
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
        return await self._wrap_call(self._api.get_info(sections, raw=raw), dict)

    async def get_control(self) -> dict[str, Any]:
        """Get current control parameters.

        Returns:
            Control parameters dictionary.

        """
        return await self._wrap_call(self._api.get_control(), dict)

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
        return await self._wrap_call(self._api.get_values(sections, raw=raw), dict)

    async def set_current(self, current: float) -> dict[str, Any]:
        """Set charging current.

        Args:
            current: Charging current in Amps (6.0-32.0).

        Returns:
            Response dictionary with confirmed value.

        """
        return await self._wrap_call(self._api.set_current(current), dict)

    async def set_charge_pause(self, pause: bool) -> dict[str, Any]:
        """Set charge pause state.

        Args:
            pause: True to pause charging, False to resume.

        Returns:
            Response dictionary with confirmed value.

        """
        return await self._wrap_call(self._api.set_charge_pause(pause), dict)

    async def set_energy_limit(self, limit: int) -> dict[str, Any]:
        """Set energy limit in Wh (0 = no limit).

        Args:
            limit: Energy limit in Watt-hours.

        Returns:
            Response dictionary with confirmed value.

        """
        return await self._wrap_call(self._api.set_energy_limit(limit), dict)

    async def set_phase_count(self, phases: int) -> dict[str, Any]:
        """Set phase count (1-3).

        Args:
            phases: Number of phases to use (1, 2, or 3).

        Returns:
            Response dictionary with confirmed value.

        """
        return await self._wrap_call(self._api.set_phase_count(phases), dict)

    async def test_connection(self) -> bool:
        """Test if we can connect to the device.

        Returns:
            True if connection successful.

        """
        return await self._wrap_call(self._api.test_connection(), bool)
