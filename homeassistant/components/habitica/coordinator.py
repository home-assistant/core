"""DataUpdateCoordinator for the Habitica integration."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
import logging
from typing import Any

from aiohttp import ClientError
from habiticalib import (
    Avatar,
    ContentData,
    GroupData,
    Habitica,
    HabiticaException,
    NotAuthorizedError,
    TaskData,
    TaskFilter,
    TooManyRequestsError,
    UserData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class HabiticaData:
    """Habitica data."""

    user: UserData
    tasks: list[TaskData]


type HabiticaConfigEntry = ConfigEntry[HabiticaDataUpdateCoordinator]


class HabiticaBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Habitica coordinator base class."""

    config_entry: HabiticaConfigEntry
    _update_interval: timedelta

    def __init__(
        self, hass: HomeAssistant, config_entry: HabiticaConfigEntry, habitica: Habitica
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

    @abstractmethod
    async def _update_data(self) -> _DataT:
        """Fetch data."""

    async def _async_update_data(self) -> _DataT:
        """Fetch the latest party data."""

        try:
            return await self._update_data()
        except TooManyRequestsError:
            _LOGGER.debug("Rate limit exceeded, will try again later")
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


class HabiticaDataUpdateCoordinator(HabiticaBaseCoordinator[HabiticaData]):
    """Habitica Data Update Coordinator."""

    _update_interval = timedelta(seconds=30)
    content: ContentData

    async def _async_setup(self) -> None:
        """Set up Habitica integration."""

        try:
            user = await self.habitica.get_user()
            self.content = (
                await self.habitica.get_content(user.data.preferences.language)
            ).data
        except NotAuthorizedError as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from e
        except TooManyRequestsError as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="setup_rate_limit_exception",
                translation_placeholders={"retry_after": str(e.retry_after)},
            ) from e
        except HabiticaException as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": str(e.error.message)},
            ) from e
        except ClientError as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": str(e)},
            ) from e

    async def _update_data(self) -> HabiticaData:
        """Fetch the latest data."""

        user = (await self.habitica.get_user()).data
        tasks = (await self.habitica.get_tasks()).data
        completed_todos = (
            await self.habitica.get_tasks(TaskFilter.COMPLETED_TODOS)
        ).data

        return HabiticaData(user=user, tasks=tasks + completed_todos)

    async def execute(self, func: Callable[[Habitica], Any]) -> None:
        """Execute an API call."""

        try:
            await func(self.habitica)
        except TooManyRequestsError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="setup_rate_limit_exception",
                translation_placeholders={"retry_after": str(e.retry_after)},
            ) from e
        except NotAuthorizedError as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_call_unallowed",
            ) from e
        except HabiticaException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": e.error.message},
            ) from e
        except ClientError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_call_exception",
                translation_placeholders={"reason": str(e)},
            ) from e
        else:
            await self.async_request_refresh()

    async def generate_avatar(self, avatar: Avatar) -> bytes:
        """Generate Avatar."""

        png = BytesIO()
        await self.habitica.generate_avatar(fp=png, avatar=avatar, fmt="PNG")

        return png.getvalue()


class HabiticaPartyCoordinator(HabiticaBaseCoordinator[GroupData]):
    """Habitica Party Coordinator."""

    _update_interval = timedelta(minutes=15)

    async def _update_data(self) -> GroupData:
        """Fetch the latest party data."""
        return (await self.habitica.get_group()).data
