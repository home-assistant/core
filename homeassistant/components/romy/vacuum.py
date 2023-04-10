"""Support for Wi-Fi enabled ROMY vacuum cleaner robots.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.romy/.
"""

from collections.abc import Mapping
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.vacuum import (
    PLATFORM_SCHEMA,
    VacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .utils import async_query

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:robot-vacuum"
PLATFORM = "romy"

FAN_SPEED_NONE = "Default"
FAN_SPEED_NORMAL = "Normal"
FAN_SPEED_SILENT = "Silent"
FAN_SPEED_INTENSIVE = "Intensive"
FAN_SPEED_SUPER_SILENT = "Super_Silent"
FAN_SPEED_HIGH = "High"
FAN_SPEED_AUTO = "Auto"

FAN_SPEEDS: list[str] = [
    FAN_SPEED_NONE,
    FAN_SPEED_NORMAL,
    FAN_SPEED_SILENT,
    FAN_SPEED_INTENSIVE,
    FAN_SPEED_SUPER_SILENT,
    FAN_SPEED_HIGH,
    FAN_SPEED_AUTO,
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=8080): cv.port,
        vol.Optional(CONF_PASSWORD): vol.All(str, vol.Length(8)),
    },
    extra=vol.ALLOW_EXTRA,
)

# Commonly supported features
SUPPORT_ROMY_ROBOT = (
    VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.SEND_COMMAND
    | VacuumEntityFeature.STATUS
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.TURN_OFF
    | VacuumEntityFeature.TURN_ON
    | VacuumEntityFeature.FAN_SPEED
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ROMY vacuum with config entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    name = config_entry.data[CONF_NAME]
    password = config_entry.data.get(CONF_PASSWORD, "")
    unique_id = ""
    model = ""
    firmware = ""

    ret, response = await async_query(hass, host, port, "get/robot_id")
    if ret:
        status = json.loads(response)
        unique_id = status["unique_id"]
        model = status["model"]
        firmware = status["firmware"]
    else:
        _LOGGER.error("Error fetching unique_id resp: %s", response)

    device_info = {
        "manufacturer": "ROMY",
        "model": model,
        "sw_version": firmware,
        "identifiers": {"serial": unique_id},
    }

    _LOGGER.info(
        "Adding ROMY vacuum robot with IP: %s PORT:%s, NAME: %s, UNIQUE_ID:%s, PASS:%s",
        host,
        port,
        name,
        unique_id,
        password,
    )
    romy_vacuum_entity = RomyRobot(host, port, name, unique_id, device_info, password)

    entities = [romy_vacuum_entity]
    async_add_entities(entities, True)


class RomyRobot(VacuumEntity):
    """Representation of a ROMY vacuum cleaner robot."""

    def __init__(
        self,
        host: str,
        port: int,
        name: str,
        unique_id: str,
        device_info: dict[str, Any],
        password: str,
    ) -> None:
        """Initialize the ROMY Robot."""
        self._host = host
        self._port = port
        self._name = name
        self._attr_unique_id = unique_id
        self._device_info = device_info
        self._password = password

        self._battery_level = None
        self._fan_speed = FAN_SPEEDS.index(FAN_SPEED_NONE)
        self._fan_speed_update = False
        self._is_on = False
        self._state_attrs: dict[str, Any] = {}
        self._status = None

    async def romy_async_query(self, command: str) -> tuple[bool, str]:
        """Send a http query."""
        ret, error = await async_query(self.hass, self._host, self._port, command)
        if ret is False and error == "403":
            _LOGGER.error("Function romy_async_query returned forbidden, try to unlock")
            # forbidden means http is locked, try to unlock again
            await self.romy_async_query(f"set/unlock_http?pass={self._password}")

        return (ret, error)

    @property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_ROMY_ROBOT

    @property
    def fan_speed(self) -> str:
        """Return the current fan speed of the vacuum cleaner."""
        return FAN_SPEEDS[self._fan_speed]

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return FAN_SPEEDS

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def status(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return self._status

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon to use for device."""
        return ICON

    @property
    def device_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the device."""
        return self._state_attrs

    # turn on -> start cleaning
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the vacuum on."""
        _LOGGER.debug("async_turn_on")
        is_on, _ = await self.romy_async_query(
            f"set/clean_start_or_continue?cleaning_parameter_set={self._fan_speed}"
        )
        if is_on:
            self._is_on = True

    # turn off -> run go_home
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the vacuum off and return to home."""
        _LOGGER.debug("async_turn_off")
        await self.async_return_to_base()

    # stop -> run stop
    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        _LOGGER.debug("async_stop")
        is_off, _ = await self.romy_async_query("set/stop")
        if is_off:
            self._is_on = False

    # pause -> run stop
    async def async_pause(self, **kwargs: Any) -> None:
        """Pause the cleaning cycle."""
        _LOGGER.debug("async_pause")
        is_off, _ = await self.romy_async_query("set/stop")
        if is_off:
            self._is_on = False

    # start_pause -> run stop or continue
    async def async_start_pause(self, **kwargs: Any) -> None:
        """Pause the cleaning task or resume it."""
        _LOGGER.debug("async_start_pause")
        if self.is_on:
            await self.async_stop()
        else:
            await self.async_turn_on()

    # return_to_base -> run go_home
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        _LOGGER.debug("async_return_to_base")
        is_on, _ = await self.romy_async_query("set/go_home")
        if is_on:
            self._is_on = False

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        _LOGGER.debug("async_set_fan_speed to %s", fan_speed)
        if fan_speed in FAN_SPEEDS:
            self._fan_speed_update = True
            self._fan_speed = FAN_SPEEDS.index(fan_speed)
            ret, response = await self.romy_async_query(
                f"set/switch_cleaning_parameter_set?cleaning_parameter_set={self._fan_speed}"
            )
            self._fan_speed_update = False
            if not ret:
                _LOGGER.error(
                    " async_set_fan_speed -> async_query response: %s", response
                )
        else:
            _LOGGER.error("No such fan speed available: %d", fan_speed)

    async def async_update(self) -> None:
        """Fetch state from the device."""
        _LOGGER.debug("async_update")

        ret, response = await self.romy_async_query("get/status")
        if ret:
            status = json.loads(response)
            self._status = status["mode"]
            self._battery_level = status["battery_level"]
        else:
            _LOGGER.error(
                "ROMY function async_update -> async_query response: %s", response
            )

        ret, response = await self.romy_async_query("get/cleaning_parameter_set")
        if ret:
            status = json.loads(response)
            # dont update if we set fan speed currently:
            if not self._fan_speed_update:
                self._fan_speed = status["cleaning_parameter_set"]
        else:
            _LOGGER.error(
                "FOMY function async_update -> async_query response: %s", response
            )
