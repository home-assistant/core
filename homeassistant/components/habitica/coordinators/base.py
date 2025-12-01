"""Base coordinator for the Habitica integration."""

from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, TypeVar

from aiohttp import ClientError
from habiticalib import Habitica, HabiticaException, TooManyRequestsError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ..const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_DataT = TypeVar("_DataT")
_LOGGER = logging.getLogger(__name__)


class HabiticaBaseCoordinator(DataUpdateCoordinator[_DataT]):  # pylint: disable=hass-enforce-class-module
    """Habitica coordinator base class."""

    config_entry: ConfigEntry
    _update_interval: timedelta
    _rate_limited_count: int

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, habitica: Habitica
    ) -> None:
        """Initialize the Habitica data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self._update_interval,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=5,
                immediate=False,
            ),
        )

        self.habitica = habitica
        self._rate_limited_count = 0

    @abstractmethod
    async def _update_data(self) -> _DataT:
        """Fetch data."""

    async def _async_update_data(self) -> _DataT:
        """Fetch the latest data."""

        try:
            result = await self._update_data()
        except TooManyRequestsError:
            _LOGGER.debug("Rate limit exceeded, will try again later")
            # NFR-3: Adaptive polling - slow down when rate limited
            self._rate_limited_count += 1
            new_interval = min(
                300,
                self._update_interval.total_seconds() * (1.5**self._rate_limited_count),
            )
            self._update_interval = timedelta(seconds=new_interval)
            _LOGGER.info(
                "Adjusted update interval to %s seconds due to rate limiting",
                new_interval,
            )
            return self.data
        except HabiticaException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": str(e.error.message)},
            ) from e
        except ClientError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": str(e)},
            ) from e
        else:
            # NFR-3: Reset rate limit counter on successful update
            self._rate_limited_count = 0
            return result
