"""DataUpdateCoordinator for the Habitica integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError
from habiticalib import (
    ContentData,
    Habitica,
    HabiticaException,
    TaskData,
    TaskFilter,
    TooManyRequestsError,
    UserData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class HabiticaData:
    """Habitica data."""

    user: UserData
    tasks: list[TaskData]


class HabiticaDataUpdateCoordinator(DataUpdateCoordinator[HabiticaData]):
    """Habitica Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, habitica: Habitica) -> None:
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
        self.habitica = habitica
        self.content: ContentData

    async def _async_update_data(self) -> HabiticaData:
        try:
            user = (await self.habitica.get_user()).data
            tasks = (await self.habitica.get_tasks()).data
            completed_todos = (
                await self.habitica.get_tasks(TaskFilter.COMPLETED_TODOS)
            ).data
            if not getattr(self, "content", None):
                self.content = (
                    await self.habitica.get_content(user.preferences.language)
                ).data
        except TooManyRequestsError:
            _LOGGER.debug("Rate limit exceeded, will try again later")
            return self.data
        except (HabiticaException, ClientError) as e:
            raise UpdateFailed(f"Unable to connect to Habitica: {e}") from e
        else:
            return HabiticaData(user=user, tasks=tasks + completed_todos)

    async def execute(
        self, func: Callable[[HabiticaDataUpdateCoordinator], Any]
    ) -> None:
        """Execute an API call."""

        try:
            await func(self)
        except TooManyRequestsError as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="setup_rate_limit_exception",
            ) from e
        except (HabiticaException, ClientError) as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
            ) from e
        else:
            await self.async_request_refresh()
