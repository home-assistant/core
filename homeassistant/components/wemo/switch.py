"""Support for WeMo switches."""

from datetime import datetime, timedelta
from typing import Any, override

from pywemo import CoffeeMaker, Insight, Maker, StandbyState, Switch

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import async_wemo_dispatcher_connect
from .coordinator import DeviceCoordinator
from .entity import WemoBinaryStateEntity

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 0

ATTR_COFFEMAKER_MODE = "coffeemaker_mode"
ATTR_CURRENT_STATE_DETAIL = "state_detail"
ATTR_ON_LATEST_TIME = "on_latest_time"
ATTR_ON_TODAY_TIME = "on_today_time"
ATTR_ON_TOTAL_TIME = "on_total_time"
ATTR_POWER_THRESHOLD = "power_threshold_w"
ATTR_SENSOR_STATE = "sensor_state"
ATTR_SWITCH_MODE = "switch_mode"

MAKER_SWITCH_MOMENTARY = "momentary"
MAKER_SWITCH_TOGGLE = "toggle"

# on_for is whole seconds and Insight is polled every SCAN_INTERVAL, so the
# computed start time jitters. Match the sensor uptime drift window.
_ON_SINCE_DRIFT = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    _config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WeMo switches."""

    async def _discovered_wemo(coordinator: DeviceCoordinator) -> None:
        """Handle a discovered Wemo device."""
        async_add_entities([WemoSwitch(coordinator)])

    await async_wemo_dispatcher_connect(hass, _discovered_wemo)


class WemoSwitch(WemoBinaryStateEntity, SwitchEntity):
    """Representation of a WeMo switch."""

    # All wemo devices used with WemoSwitch are subclasses of Switch.
    wemo: Switch
    _on_since: datetime | None = None
    _on_for: int | None = None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        attr: dict[str, Any] = {}
        if isinstance(self.wemo, Maker):
            # Is the maker sensor on or off.
            if self.wemo.has_sensor:
                # Note a state of 1 matches the WeMo app 'not triggered'!
                if self.wemo.sensor_state:
                    attr[ATTR_SENSOR_STATE] = STATE_OFF
                else:
                    attr[ATTR_SENSOR_STATE] = STATE_ON

            # Is the maker switch configured as toggle(0) or momentary (1).
            if self.wemo.switch_mode:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_MOMENTARY
            else:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_TOGGLE

        if isinstance(self.wemo, (Insight, CoffeeMaker)):
            attr[ATTR_CURRENT_STATE_DETAIL] = self.detail_state

        if isinstance(self.wemo, Insight):
            if (on_since := self._absolute_on_since()) is not None:
                attr[ATTR_ON_LATEST_TIME] = on_since
            # today_on_time and total_on_time are cumulative durations, not
            # points in time, so they stay relative strings.
            attr[ATTR_ON_TODAY_TIME] = self.as_uptime(self.wemo.today_on_time)
            attr[ATTR_ON_TOTAL_TIME] = self.as_uptime(self.wemo.total_on_time)
            attr[ATTR_POWER_THRESHOLD] = self.wemo.threshold_power_watts

        if isinstance(self.wemo, CoffeeMaker):
            attr[ATTR_COFFEMAKER_MODE] = self.wemo.mode

        return attr

    def _absolute_on_since(self) -> datetime | None:
        """Return when the current on period started.

        ``on_for`` increases only while the outlet is on or in standby, so
        subtracting it from now is an absolute start time. While off it is the
        finished length of the last on period and would walk forward every poll.
        A decrease while still on is a new period whose off poll was missed.
        """
        wemo = self.wemo
        if not isinstance(wemo, Insight):
            return None
        if wemo.standby_state not in (StandbyState.ON, StandbyState.STANDBY):
            self._on_since = None
            self._on_for = None
            return None

        on_for = wemo.on_for
        candidate = (dt_util.utcnow() - timedelta(seconds=on_for)).replace(
            microsecond=0
        )
        # Drop the cached start before the drift window. A shorter on_for is a
        # new period, and the new start can still fall inside that window.
        if self._on_for is not None and on_for < self._on_for:
            self._on_since = None
        self._on_for = on_for
        previous = self._on_since
        if previous is not None and abs(candidate - previous) <= _ON_SINCE_DRIFT:
            return previous
        self._on_since = candidate
        return candidate

    @staticmethod
    def as_uptime(_seconds: int) -> str:
        """Format seconds into uptime string in the format: 00d 00h 00m 00s."""
        uptime = datetime(1, 1, 1) + timedelta(seconds=_seconds)
        return (
            f"{uptime.day - 1:0>2d}d {uptime.hour:0>2d}h "
            f"{uptime.minute:0>2d}m {uptime.second:0>2d}s"
        )

    @property
    def detail_state(self) -> str:
        """Return the state of the device."""
        if isinstance(self.wemo, CoffeeMaker):
            return self.wemo.mode_string
        if isinstance(self.wemo, Insight):
            standby_state = self.wemo.standby_state
            if standby_state == StandbyState.ON:
                return STATE_ON
            if standby_state == StandbyState.OFF:
                return STATE_OFF
            if standby_state == StandbyState.STANDBY:
                return STATE_STANDBY
            return STATE_UNKNOWN
        # Unreachable code statement.
        raise RuntimeError

    @property
    @override
    def icon(self) -> str | None:
        """Return the icon of device based on its type."""
        if isinstance(self.wemo, CoffeeMaker):
            return "mdi:coffee"
        return None

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_wemo_call("turn on", self.wemo.on)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_wemo_call("turn off", self.wemo.off)
