"""Demo platform for the vacuum component."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.vacuum import (
    ATTR_CLEANED_AREA,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

SUPPORT_MINIMAL_SERVICES = VacuumEntityFeature.TURN_ON | VacuumEntityFeature.TURN_OFF

SUPPORT_BASIC_SERVICES = (
    VacuumEntityFeature.TURN_ON
    | VacuumEntityFeature.TURN_OFF
    | VacuumEntityFeature.STATUS
    | VacuumEntityFeature.BATTERY
)

SUPPORT_MOST_SERVICES = (
    VacuumEntityFeature.TURN_ON
    | VacuumEntityFeature.TURN_OFF
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.STATUS
    | VacuumEntityFeature.BATTERY
)

SUPPORT_ALL_SERVICES = (
    VacuumEntityFeature.TURN_ON
    | VacuumEntityFeature.TURN_OFF
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.SEND_COMMAND
    | VacuumEntityFeature.LOCATE
    | VacuumEntityFeature.STATUS
    | VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.CLEAN_SPOT
)

SUPPORT_STATE_SERVICES = (
    VacuumEntityFeature.STATE
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.CLEAN_SPOT
    | VacuumEntityFeature.START
)

FAN_SPEEDS = ["min", "medium", "high", "max"]
DEMO_VACUUM_COMPLETE = "0_Ground_floor"
DEMO_VACUUM_MOST = "1_First_floor"
DEMO_VACUUM_BASIC = "2_Second_floor"
DEMO_VACUUM_MINIMAL = "3_Third_floor"
DEMO_VACUUM_NONE = "4_Fourth_floor"
DEMO_VACUUM_STATE = "5_Fifth_floor"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo vacuums."""
    async_add_entities(
        [
            DemoVacuum(DEMO_VACUUM_COMPLETE, SUPPORT_ALL_SERVICES),
            DemoVacuum(DEMO_VACUUM_MOST, SUPPORT_MOST_SERVICES),
            DemoVacuum(DEMO_VACUUM_BASIC, SUPPORT_BASIC_SERVICES),
            DemoVacuum(DEMO_VACUUM_MINIMAL, SUPPORT_MINIMAL_SERVICES),
            DemoVacuum(DEMO_VACUUM_NONE, VacuumEntityFeature(0)),
            StateDemoVacuum(DEMO_VACUUM_STATE),
        ]
    )


class DemoVacuum(VacuumEntity):
    """Representation of a demo vacuum."""

    _attr_should_poll = False

    def __init__(self, name: str, supported_features: VacuumEntityFeature) -> None:
        """Initialize the vacuum."""
        self._attr_name = name
        self._attr_supported_features = supported_features
        self._state = False
        self._status = "Charging"
        self._fan_speed = FAN_SPEEDS[1]
        self._cleaned_area: float = 0
        self._battery_level = 100

    @property
    def is_on(self) -> bool:
        """Return true if vacuum is on."""
        return self._state

    @property
    def status(self) -> str:
        """Return the status of the vacuum."""
        return self._status

    @property
    def fan_speed(self) -> str:
        """Return the status of the vacuum."""
        return self._fan_speed

    @property
    def fan_speed_list(self) -> list[str]:
        """Return the status of the vacuum."""
        return FAN_SPEEDS

    @property
    def battery_level(self) -> int:
        """Return the status of the vacuum."""
        return max(0, min(100, self._battery_level))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attributes."""
        return {ATTR_CLEANED_AREA: round(self._cleaned_area, 2)}

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the vacuum on."""
        if self.supported_features & VacuumEntityFeature.TURN_ON == 0:
            return

        self._state = True
        self._cleaned_area += 5.32
        self._battery_level -= 2
        self._status = "Cleaning"
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the vacuum off."""
        if self.supported_features & VacuumEntityFeature.TURN_OFF == 0:
            return

        self._state = False
        self._status = "Charging"
        self.schedule_update_ha_state()

    def stop(self, **kwargs: Any) -> None:
        """Stop the vacuum."""
        if self.supported_features & VacuumEntityFeature.STOP == 0:
            return

        self._state = False
        self._status = "Stopping the current task"
        self.schedule_update_ha_state()

    def clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        if self.supported_features & VacuumEntityFeature.CLEAN_SPOT == 0:
            return

        self._state = True
        self._cleaned_area += 1.32
        self._battery_level -= 1
        self._status = "Cleaning spot"
        self.schedule_update_ha_state()

    def locate(self, **kwargs: Any) -> None:
        """Locate the vacuum (usually by playing a song)."""
        if self.supported_features & VacuumEntityFeature.LOCATE == 0:
            return

        self._status = "Hi, I'm over here!"
        self.schedule_update_ha_state()

    def start_pause(self, **kwargs: Any) -> None:
        """Start, pause or resume the cleaning task."""
        if self.supported_features & VacuumEntityFeature.PAUSE == 0:
            return

        self._state = not self._state
        if self._state:
            self._status = "Resuming the current task"
            self._cleaned_area += 1.32
            self._battery_level -= 1
        else:
            self._status = "Pausing the current task"
        self.schedule_update_ha_state()

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the vacuum's fan speed."""
        if self.supported_features & VacuumEntityFeature.FAN_SPEED == 0:
            return

        if fan_speed in self.fan_speed_list:
            self._fan_speed = fan_speed
            self.schedule_update_ha_state()

    def return_to_base(self, **kwargs: Any) -> None:
        """Tell the vacuum to return to its dock."""
        if self.supported_features & VacuumEntityFeature.RETURN_HOME == 0:
            return

        self._state = False
        self._status = "Returning home..."
        self._battery_level += 5
        self.schedule_update_ha_state()

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to the vacuum."""
        if self.supported_features & VacuumEntityFeature.SEND_COMMAND == 0:
            return

        self._status = f"Executing {command}({params})"
        self._state = True
        self.schedule_update_ha_state()


class StateDemoVacuum(StateVacuumEntity):
    """Representation of a demo vacuum supporting states."""

    _attr_should_poll = False
    _attr_supported_features = SUPPORT_STATE_SERVICES

    def __init__(self, name: str) -> None:
        """Initialize the vacuum."""
        self._attr_name = name
        self._state = STATE_DOCKED
        self._fan_speed = FAN_SPEEDS[1]
        self._cleaned_area: float = 0
        self._battery_level = 100

    @property
    def state(self) -> str:
        """Return the current state of the vacuum."""
        return self._state

    @property
    def battery_level(self) -> int:
        """Return the current battery level of the vacuum."""
        return max(0, min(100, self._battery_level))

    @property
    def fan_speed(self) -> str:
        """Return the current fan speed of the vacuum."""
        return self._fan_speed

    @property
    def fan_speed_list(self) -> list[str]:
        """Return the list of supported fan speeds."""
        return FAN_SPEEDS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attributes."""
        return {ATTR_CLEANED_AREA: round(self._cleaned_area, 2)}

    def start(self) -> None:
        """Start or resume the cleaning task."""
        if self.supported_features & VacuumEntityFeature.START == 0:
            return

        if self._state != STATE_CLEANING:
            self._state = STATE_CLEANING
            self._cleaned_area += 1.32
            self._battery_level -= 1
            self.schedule_update_ha_state()

    def pause(self) -> None:
        """Pause the cleaning task."""
        if self.supported_features & VacuumEntityFeature.PAUSE == 0:
            return

        if self._state == STATE_CLEANING:
            self._state = STATE_PAUSED
            self.schedule_update_ha_state()

    def stop(self, **kwargs: Any) -> None:
        """Stop the cleaning task, do not return to dock."""
        if self.supported_features & VacuumEntityFeature.STOP == 0:
            return

        self._state = STATE_IDLE
        self.schedule_update_ha_state()

    def return_to_base(self, **kwargs: Any) -> None:
        """Return dock to charging base."""
        if self.supported_features & VacuumEntityFeature.RETURN_HOME == 0:
            return

        self._state = STATE_RETURNING
        self.schedule_update_ha_state()

        event.call_later(self.hass, 30, self.__set_state_to_dock)

    def clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        if self.supported_features & VacuumEntityFeature.CLEAN_SPOT == 0:
            return

        self._state = STATE_CLEANING
        self._cleaned_area += 1.32
        self._battery_level -= 1
        self.schedule_update_ha_state()

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the vacuum's fan speed."""
        if self.supported_features & VacuumEntityFeature.FAN_SPEED == 0:
            return

        if fan_speed in self.fan_speed_list:
            self._fan_speed = fan_speed
            self.schedule_update_ha_state()

    def __set_state_to_dock(self, _: datetime) -> None:
        self._state = STATE_DOCKED
        self.schedule_update_ha_state()
