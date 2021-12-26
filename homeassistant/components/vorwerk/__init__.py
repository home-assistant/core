"""Support for botvac connected Vorwerk vacuum cleaners."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from pybotvac.exceptions import NeatoException, NeatoRobotException
from pybotvac.robot import Robot
from pybotvac.vorwerk import Vorwerk
import voluptuous as vol

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ACTION,
    ALERTS,
    ERRORS,
    MIN_TIME_BETWEEN_UPDATES,
    MODE,
    ROBOT_CLEANING_ACTIONS,
    ROBOT_STATE_BUSY,
    ROBOT_STATE_ERROR,
    ROBOT_STATE_IDLE,
    ROBOT_STATE_PAUSE,
    VORWERK_DOMAIN,
    VORWERK_PLATFORMS,
    VORWERK_ROBOT_API,
    VORWERK_ROBOT_COORDINATOR,
    VORWERK_ROBOT_ENDPOINT,
    VORWERK_ROBOT_NAME,
    VORWERK_ROBOT_SECRET,
    VORWERK_ROBOT_SERIAL,
    VORWERK_ROBOT_TRAITS,
    VORWERK_ROBOTS,
)

_LOGGER = logging.getLogger(__name__)


VORWERK_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(VORWERK_ROBOT_NAME): cv.string,
            vol.Required(VORWERK_ROBOT_SERIAL): cv.string,
            vol.Required(VORWERK_ROBOT_SECRET): cv.string,
            vol.Optional(
                VORWERK_ROBOT_ENDPOINT, default="https://nucleo.ksecosys.com:4443"
            ): cv.string,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    {VORWERK_DOMAIN: vol.Schema(vol.All(cv.ensure_list, [VORWERK_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Vorwerk component."""
    hass.data[VORWERK_DOMAIN] = {}

    if VORWERK_DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                VORWERK_DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[VORWERK_DOMAIN],
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    robots = await _async_create_robots(hass, entry.data[VORWERK_ROBOTS])

    robot_states = [VorwerkState(robot) for robot in robots]

    hass.data[VORWERK_DOMAIN][entry.entry_id] = {
        VORWERK_ROBOTS: [
            {
                VORWERK_ROBOT_API: r,
                VORWERK_ROBOT_COORDINATOR: _create_coordinator(hass, r),
            }
            for r in robot_states
        ]
    }

    for component in VORWERK_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


def _create_coordinator(
    hass: HomeAssistantType, robot_state: VorwerkState
) -> DataUpdateCoordinator:
    async def async_update_data():
        """Fetch data from API endpoint."""
        await hass.async_add_executor_job(robot_state.update)

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=robot_state.robot.name,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )


async def _async_create_robots(hass, robot_confs):
    def create_robot(config):
        return Robot(
            serial=config[VORWERK_ROBOT_SERIAL],
            secret=config[VORWERK_ROBOT_SECRET],
            traits=config.get(VORWERK_ROBOT_TRAITS, []),
            vendor=Vorwerk(),
            name=config[VORWERK_ROBOT_NAME],
            endpoint=config[VORWERK_ROBOT_ENDPOINT],
        )

    robots = []
    try:
        robots = await asyncio.gather(
            *(
                hass.async_add_executor_job(create_robot, robot_conf)
                for robot_conf in robot_confs
            ),
            return_exceptions=False,
        )
    except NeatoException as ex:
        _LOGGER.error("Failed to connect to robots: %s", ex)
        raise ConfigEntryNotReady from ex
    return robots


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_ok: bool = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in VORWERK_PLATFORMS
            )
        )
    )
    if unload_ok:
        hass.data[VORWERK_DOMAIN].pop(entry.entry_id)
    return unload_ok


class VorwerkState:
    """Class to convert robot_state dict to more useful object."""

    def __init__(self, robot: Robot) -> None:
        """Initialize new vorwerk vacuum state."""
        self.robot = robot
        self.robot_state: dict[Any, Any] = {}
        self.robot_info: dict[Any, Any] = {}

    @property
    def available(self) -> bool:
        """Return true when robot state is available."""
        return bool(self.robot_state)

    def update(self):
        """Update robot state and robot info."""
        _LOGGER.debug("Running Vorwerk Vacuums update for '%s'", self.robot.name)
        self._update_robot_info()
        self._update_state()

    def _update_robot_info(self):
        try:
            if not self.robot_info:
                self.robot_info = self.robot.get_general_info().json().get("data")
        except NeatoRobotException:
            _LOGGER.warning("Couldn't fetch robot information of %s", self.robot.name)

    def _update_state(self):
        try:
            self.robot_state = self.robot.state
            _LOGGER.debug(self.robot_state)
        except NeatoRobotException as ex:
            if self.available:  # print only once when available
                _LOGGER.error(
                    "Vorwerk vacuum connection error for '%s': %s", self.robot.name, ex
                )
            self.robot_state = {}
            return

    @property
    def docked(self) -> bool | None:
        """Vacuum is docked."""
        if not self.available:
            return None
        return (
            self.robot_state["state"] == ROBOT_STATE_IDLE
            and self.robot_state["details"]["isDocked"]
        )

    @property
    def charging(self) -> bool | None:
        """Vacuum is charging."""
        if not self.available:
            return None
        return (
            self.robot_state.get("state") == ROBOT_STATE_IDLE
            and self.robot_state["details"]["isCharging"]
        )

    @property
    def state(self) -> str | None:
        """Return Home Assistant vacuum state."""
        if not self.available:
            return None
        robot_state = self.robot_state.get("state")
        state = None
        if self.charging or self.docked:
            state = STATE_DOCKED
        elif robot_state == ROBOT_STATE_IDLE:
            state = STATE_IDLE
        elif robot_state == ROBOT_STATE_BUSY:
            action = self.robot_state.get("action")
            if action in ROBOT_CLEANING_ACTIONS:
                state = STATE_CLEANING
            else:
                state = STATE_RETURNING
        elif robot_state == ROBOT_STATE_PAUSE:
            state = STATE_PAUSED
        elif robot_state == ROBOT_STATE_ERROR:
            state = STATE_ERROR
        return state

    @property
    def alert(self) -> str | None:
        """Return vacuum alert message."""
        if not self.available:
            return None
        if "alert" in self.robot_state:
            return ALERTS.get(self.robot_state["alert"], self.robot_state["alert"])
        return None

    @property
    def status(self) -> str | None:
        """Return vacuum status message."""
        if not self.available:
            return None

        status = None
        if self.state == STATE_ERROR:
            status = self._error_status()
        elif self.alert:
            status = self.alert
        elif self.state == STATE_DOCKED:
            if self.charging:
                status = "Charging"
            if self.docked:
                status = "Docked"
        elif self.state == STATE_IDLE:
            status = "Stopped"
        elif self.state == STATE_CLEANING:
            status = self._cleaning_status()
        elif self.state == STATE_PAUSED:
            status = "Paused"
        elif self.state == STATE_RETURNING:
            status = "Returning"

        return status

    def _error_status(self):
        """Return error status."""
        return ERRORS.get(self.robot_state["error"], self.robot_state["error"])

    def _cleaning_status(self):
        """Return cleaning status."""
        status_items = [
            MODE.get(self.robot_state["cleaning"]["mode"]),
            ACTION.get(self.robot_state["action"]),
        ]
        if (
            "boundary" in self.robot_state["cleaning"]
            and "name" in self.robot_state["cleaning"]["boundary"]
        ):
            status_items.append(self.robot_state["cleaning"]["boundary"]["name"])
        return " ".join(s for s in status_items if s)

    @property
    def battery_level(self) -> str | None:
        """Return the battery level of the vacuum cleaner."""
        if not self.available:
            return None
        return self.robot_state["details"]["charge"]

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for robot."""
        return DeviceInfo(
            identifiers={(VORWERK_DOMAIN, self.robot.serial)},
            manufacturer=self.robot_info["battery"]["vendor"] if self.robot_info else None,
            model=self.robot_info["model"] if self.robot_info else None,
            name=self.robot.name,
            sw_version=self.robot_info["firmware"] if self.robot_info else None,
        )

    @property
    def schedule_enabled(self):
        """Return True when schedule is enabled."""
        if not self.available:
            return None
        return bool(self.robot_state["details"]["isScheduleEnabled"])
