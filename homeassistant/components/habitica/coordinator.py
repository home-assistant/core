"""DataUpdateCoordinator for the Habitica integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
from io import BytesIO
import logging
from typing import Any

from aiohttp import ClientResponseError
from habiticalib import Habitica
from habiticalib.types import UserStyles
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

    def __init__(
        self, hass: HomeAssistant, habitipy: HabitipyAsync, habitica: Habitica
    ) -> None:
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
        self.content: dict[str, Any] = {}
        self.habitica = habitica

    async def _async_update_data(self) -> HabiticaData:
        try:
            user_response = await self.api.user.get()
            tasks_response = await self.api.tasks.user.get()
            tasks_response.extend(await self.api.tasks.user.get(type="completedTodos"))
            if not self.content:
                self.content = await self.api.content.get(
                    language=user_response["preferences"]["language"]
                )
        except ClientResponseError as error:
            if error.status == HTTPStatus.TOO_MANY_REQUESTS:
                _LOGGER.debug("Rate limit exceeded, will try again later")
                return self.data
            raise UpdateFailed(f"Unable to connect to Habitica: {error}") from error

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

    async def generate_avatar(self, user_styles: UserStyles) -> bytes:
        """Generate Avatar."""

        avatar = BytesIO()
        await self.habitica.generate_avatar(
            fp=avatar, user_styles=user_styles, fmt="PNG"
        )

        return avatar.getvalue()
