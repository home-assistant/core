"""A wrapper 'hub' for the Litter-Robot API and base entity for common attributes."""
from __future__ import annotations

from datetime import time, timedelta
import logging
from types import MethodType
from typing import Any

import pylitterbot
from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

REFRESH_WAIT_TIME = 12
UPDATE_INTERVAL = 10


class LitterRobotHub:
    """A Litter-Robot hub wrapper class."""

    def __init__(self, hass: HomeAssistant, data: dict):
        """Initialize the Litter-Robot hub."""
        self._data = data
        self.account = None
        self.logged_in = False

        async def _async_update_data():
            """Update all device states from the Litter-Robot API."""
            await self.account.refresh_robots()
            return True

        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=_async_update_data,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def login(self, load_robots: bool = False):
        """Login to Litter-Robot."""
        self.logged_in = False
        self.account = pylitterbot.Account()
        try:
            await self.account.connect(
                username=self._data[CONF_USERNAME],
                password=self._data[CONF_PASSWORD],
                load_robots=load_robots,
            )
            self.logged_in = True
            return self.logged_in
        except LitterRobotLoginException as ex:
            _LOGGER.error("Invalid credentials")
            raise ex
        except LitterRobotException as ex:
            _LOGGER.error("Unable to connect to Litter-Robot API")
            raise ex


class LitterRobotEntity(CoordinatorEntity):
    """Generic Litter-Robot entity representing common data and methods."""

    def __init__(self, robot: pylitterbot.Robot, entity_type: str, hub: LitterRobotHub):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(hub.coordinator)
        self.robot = robot
        self.entity_type = entity_type
        self.hub = hub

    @property
    def name(self):
        """Return the name of this entity."""
        return f"{self.robot.name} {self.entity_type}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.robot.serial}-{self.entity_type}"

    @property
    def device_info(self):
        """Return the device information for a Litter-Robot."""
        return {
            "identifiers": {(DOMAIN, self.robot.serial)},
            "name": self.robot.name,
            "manufacturer": "Litter-Robot",
            "model": self.robot.model,
        }

    async def perform_action_and_refresh(self, action: MethodType, *args: Any):
        """Perform an action and initiates a refresh of the robot data after a few seconds."""

        async def async_call_later_callback(*_) -> None:
            await self.hub.coordinator.async_request_refresh()

        await action(*args)
        async_call_later(self.hass, REFRESH_WAIT_TIME, async_call_later_callback)

    @staticmethod
    def parse_time_at_default_timezone(time_str: str) -> time | None:
        """Parse a time string and add default timezone."""
        parsed_time = dt_util.parse_time(time_str)

        if parsed_time is None:
            return None

        return (
            dt_util.start_of_local_day()
            .replace(
                hour=parsed_time.hour,
                minute=parsed_time.minute,
                second=parsed_time.second,
            )
            .timetz()
        )
