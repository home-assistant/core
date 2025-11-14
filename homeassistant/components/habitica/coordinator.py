"""DataUpdateCoordinator for from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.debouncer import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# FR-5: 48-hour threshold for unscored task alerts
UNSCORED_TASK_ALERT_HOURS = 48


from __future__ import annotations


from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
import logging
from typing import Any
from uuid import UUID

import habitipy  # Make sure this is imported
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
    habits: list[TaskData]  # Add habits specifically for sensor platform
    habits: list[TaskData]  # Add habits specifically for sensor platform


@dataclass
class HabiticaPartyData:
    """Habitica party data."""

    party: GroupData
    members: dict[UUID, UserData]


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
            result = await self._update_data()
            # NFR-3: Reset rate limit counter on successful update
            if hasattr(self, '_rate_limited_count'):
                self._rate_limited_count = 0
            return result
        except TooManyRequestsError:
            _LOGGER.debug("Rate limit exceeded, will try again later")
            # NFR-3: Adaptive polling - slow down when rate limited
            if hasattr(self, '_rate_limited_count'):
                self._rate_limited_count += 1
                new_interval = min(300, self._update_interval.total_seconds() * (1.5 ** self._rate_limited_count))
                self._update_interval = timedelta(seconds=new_interval)
                _LOGGER.info("Adjusted update interval to %s seconds due to rate limiting", new_interval)
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

    _update_interval = timedelta(seconds=30)  # Base interval
    content: ContentData
    _rate_limited_count: int = 0
    _last_activity_time: datetime | None = None

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
        
        # Fetch habit tasks specifically (fulfills ADR2)
        habits = (await self.habitica.get_tasks(TaskFilter.HABITS)).data

        # FR-5: Check for unscored tasks and fire automation events
        await self._check_unscored_tasks(tasks)

        return HabiticaData(user=user, tasks=tasks + completed_todos, habits=habits)

    async def _check_unscored_tasks(self, tasks: list[TaskData]) -> None:
        """Check for unscored tasks and fire automation events (FR-5)."""
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        threshold_hours = UNSCORED_TASK_ALERT_HOURS
        
        for task in tasks:
            # Skip completed tasks
            if getattr(task, 'completed', False):
                continue
                
            # Check if task has updatedAt timestamp
            if not hasattr(task, 'updatedAt') or not task.updatedAt:
                continue
                
            # Calculate hours since last update
            try:
                last_updated = task.updatedAt
                if not last_updated.tzinfo:
                    last_updated = last_updated.replace(tzinfo=timezone.utc)
                    
                hours_since_update = (now - last_updated).total_seconds() / 3600
                
                # Fire event if task hasn't been updated in 48+ hours
                if hours_since_update >= threshold_hours:
                    self.hass.bus.async_fire(
                        "habitica_unscored_task_alert",
                        {
                            "task_id": str(task.id),
                            "task_text": task.text,
                            "task_type": task.Type.value if task.Type else "unknown",
                            "hours_since_update": round(hours_since_update, 1),
                            "config_entry_id": self.config_entry.entry_id,
                            "user_id": str(self.data.user.id) if self.data else None,
                        },
                    )
                    _LOGGER.info(
                        "Fired unscored task alert for '%s' (%.1f hours overdue)",
                        task.text,
                        hours_since_update
                    )
            except (AttributeError, TypeError, ValueError) as e:
                _LOGGER.debug("Error checking task %s update time: %s", task.text, e)
                continue

    def _adjust_polling_for_activity(self) -> None:
        """Adjust polling interval based on user activity (NFR-3)."""
        from datetime import timezone
        
        now = datetime.now(timezone.utc)
        base_interval = 30  # Base 30 seconds
        
        # If we have recent activity, poll more frequently
        if self._last_activity_time:
            time_since_activity = (now - self._last_activity_time).total_seconds()
            
            if time_since_activity < 300:  # 5 minutes
                # Recent activity - poll every 15 seconds
                new_interval = 15
            elif time_since_activity < 1800:  # 30 minutes  
                # Moderate activity - poll every 30 seconds (default)
                new_interval = base_interval
            elif time_since_activity < 3600:  # 1 hour
                # Low activity - poll every 60 seconds
                new_interval = 60
            else:
                # No recent activity - poll every 120 seconds
                new_interval = 120
                
            # Don't override if we're rate limited
            if self._rate_limited_count == 0:
                self._update_interval = timedelta(seconds=new_interval)

    async def execute(self, func: Callable[[Habitica], Any]) -> None:
        """Execute an API call."""
        from datetime import timezone
        
        # Track user activity for adaptive polling (NFR-3)
        self._last_activity_time = datetime.now(timezone.utc)

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
            # Adjust polling based on activity
            self._adjust_polling_for_activity()
            await self.async_request_refresh()

    async def generate_avatar(self, avatar: Avatar) -> bytes:
        """Generate Avatar."""

        png = BytesIO()
        await self.habitica.generate_avatar(fp=png, avatar=avatar, fmt="PNG")

        return png.getvalue()


class HabiticaPartyCoordinator(HabiticaBaseCoordinator[HabiticaPartyData]):
    """Habitica Party Coordinator."""

    _update_interval = timedelta(minutes=15)

    async def _update_data(self) -> HabiticaPartyData:
        """Fetch the latest party data."""

        return HabiticaPartyData(
            party=(await self.habitica.get_group()).data,
            members={
                member.id: member
                for member in (
                    await self.habitica.get_group_members(public_fields=True)
                ).data
                if member.id
            },
        )
