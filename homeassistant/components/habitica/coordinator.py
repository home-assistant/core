"""Data Coordinator for Habitica."""

from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.util import Throttle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)


class HabitipyData:
    """Habitica API user data cache."""

    tasks: dict[str, Any] = {}

    def __init__(self, api) -> None:
        """Habitica API user data cache."""
        self.api = api
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self):
        """Get a new fix from Habitica servers."""
        try:
            self.data = await self.api.user.get()
        except ClientResponseError as error:
            if error.status == HTTPStatus.TOO_MANY_REQUESTS:
                _LOGGER.warning(
                    (
                        "Sensor data update for %s has too many API requests;"
                        " Skipping the update"
                    ),
                    DOMAIN,
                )
            else:
                _LOGGER.error(
                    "Count not update sensor data for %s (%s)",
                    DOMAIN,
                    error,
                )

        for task_type in ("habits", "dailys", "todos", "rewards", "completedTodos"):
            try:
                self.tasks[task_type] = await self.api.tasks.user.get(type=task_type)
            except ClientResponseError as error:
                if error.status == HTTPStatus.TOO_MANY_REQUESTS:
                    _LOGGER.warning(
                        (
                            "Sensor data update for %s has too many API requests;"
                            " Skipping the update"
                        ),
                        DOMAIN,
                    )
                else:
                    _LOGGER.error(
                        "Count not update sensor data for %s (%s)",
                        DOMAIN,
                        error,
                    )
