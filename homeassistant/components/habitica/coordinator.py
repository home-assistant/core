"""DataUpdateCoordinator for the Habitica integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
from habitipy.aio import HabitipyAsync

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class HabiticaData:
    """Coordinator data class."""

    user: dict[str, Any]
    tasks: list[dict]


class HabiticaDataUpdateCoordinator(DataUpdateCoordinator[HabiticaData]):
    """Habitica Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, habitipy: HabitipyAsync) -> None:
        """Initialize the Habitica data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=5,
                immediate=False,
            ),
        )
        self.api = habitipy

    async def _async_update_data(self) -> HabiticaData:
        try:
            user_response = await self.api.user.get()
            tasks_response = await self.api.tasks.user.get()
            tasks_response.extend(await self.api.tasks.user.get(type="completedTodos"))
        except ClientResponseError as error:
            if error.status == HTTPStatus.TOO_MANY_REQUESTS:
                _LOGGER.debug("Currently rate limited, skipping update")
                return self.data
            raise UpdateFailed(f"Error communicating with API: {error}") from error

        return HabiticaData(user=user_response, tasks=tasks_response)

    async def execute(
        self, func: Callable[[HabiticaDataUpdateCoordinator], Any]
    ) -> None:
        """Execute an API call."""

        try:
            await func(self)
        except ClientResponseError as e:
            if e.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setup_rate_limit_exception",
                ) from e
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            await self.async_request_refresh()
