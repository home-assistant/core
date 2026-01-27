"""DataUpdateCoordinator for NRGkick integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Concatenate

import aiohttp
from nrgkick_api import (
    NRGkickAPI,
    NRGkickAPIDisabledError,
    NRGkickAuthenticationError,
    NRGkickConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Type alias for typed config entry with runtime_data.
type NRGkickConfigEntry = ConfigEntry[NRGkickDataUpdateCoordinator]


def _coordinator_exception_handler[
    _DataUpdateCoordinatorT: DataUpdateCoordinator[Any],
    **_P,
](
    func: Callable[Concatenate[_DataUpdateCoordinatorT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_DataUpdateCoordinatorT, _P], Coroutine[Any, Any, Any]]:
    """Handle exceptions within the update handler of a coordinator."""

    async def handler(
        self: _DataUpdateCoordinatorT, /, *args: _P.args, **kwargs: _P.kwargs
    ) -> Any:
        try:
            return await func(self, *args, **kwargs)
        except NRGkickAuthenticationError as error:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from error
        except NRGkickAPIDisabledError as error:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="json_api_disabled",
            ) from error
        except NRGkickConnectionError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error
        except (TimeoutError, aiohttp.ClientError, OSError) as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler


@dataclass(slots=True)
class NRGkickData:
    """Container for coordinator data."""

    info: dict[str, Any]
    control: dict[str, Any]
    values: dict[str, Any]


class NRGkickDataUpdateCoordinator(DataUpdateCoordinator[NRGkickData]):
    """Class to manage fetching NRGkick data from the API."""

    config_entry: NRGkickConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: NRGkickAPI, entry: NRGkickConfigEntry
    ) -> None:
        """Initialize."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
            always_update=False,
        )

    @_coordinator_exception_handler
    async def _async_update_data(self) -> NRGkickData:
        """Update data via library."""
        info = await self.api.get_info(raw=True)
        control = await self.api.get_control()
        values = await self.api.get_values(raw=True)

        return NRGkickData(info=info, control=control, values=values)
