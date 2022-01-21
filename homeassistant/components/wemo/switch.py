"""Support for WeMo switches."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, cast

from pywemo import CoffeeMaker, Insight, Maker

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import convert

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoBinaryStateEntity
from .wemo_device import DeviceCoordinator

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 0

# The WEMO_ constants below come from pywemo itself
ATTR_SENSOR_STATE = "sensor_state"
ATTR_SWITCH_MODE = "switch_mode"
ATTR_CURRENT_STATE_DETAIL = "state_detail"
ATTR_COFFEMAKER_MODE = "coffeemaker_mode"

MAKER_SWITCH_MOMENTARY = "momentary"
MAKER_SWITCH_TOGGLE = "toggle"

WEMO_ON = 1
WEMO_OFF = 0
WEMO_STANDBY = 8


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WeMo switches."""

    async def _discovered_wemo(coordinator: DeviceCoordinator) -> None:
        """Handle a discovered Wemo device."""
        async_add_entities([WemoSwitch(coordinator)])

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.switch", _discovered_wemo)

    await asyncio.gather(
        *(
            _discovered_wemo(coordinator)
            for coordinator in hass.data[WEMO_DOMAIN]["pending"].pop("switch")
        )
    )


class WemoSwitch(WemoBinaryStateEntity, SwitchEntity):
    """Representation of a WeMo switch."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        attr: dict[str, Any] = {}
        if isinstance(self.wemo, Maker):
            # Is the maker sensor on or off.
            if self.wemo.maker_params["hassensor"]:
                # Note a state of 1 matches the WeMo app 'not triggered'!
                if self.wemo.maker_params["sensorstate"]:
                    attr[ATTR_SENSOR_STATE] = STATE_OFF
                else:
                    attr[ATTR_SENSOR_STATE] = STATE_ON

            # Is the maker switch configured as toggle(0) or momentary (1).
            if self.wemo.maker_params["switchmode"]:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_MOMENTARY
            else:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_TOGGLE

        if isinstance(self.wemo, (Insight, CoffeeMaker)):
            attr[ATTR_CURRENT_STATE_DETAIL] = self.detail_state

        if isinstance(self.wemo, Insight):
            attr["on_latest_time"] = WemoSwitch.as_uptime(
                self.wemo.insight_params.get("onfor", 0)
            )
            attr["on_today_time"] = WemoSwitch.as_uptime(
                self.wemo.insight_params.get("ontoday", 0)
            )
            attr["on_total_time"] = WemoSwitch.as_uptime(
                self.wemo.insight_params.get("ontotal", 0)
            )
            threshold = convert(
                self.wemo.insight_params.get("powerthreshold"), float, 0.0
            )
            assert isinstance(threshold, float)
            attr["power_threshold_w"] = threshold / 1000.0

        if isinstance(self.wemo, CoffeeMaker):
            attr[ATTR_COFFEMAKER_MODE] = self.wemo.mode

        return attr

    @staticmethod
    def as_uptime(_seconds: int) -> str:
        """Format seconds into uptime string in the format: 00d 00h 00m 00s."""
        uptime = datetime(1, 1, 1) + timedelta(seconds=_seconds)
        return "{:0>2d}d {:0>2d}h {:0>2d}m {:0>2d}s".format(
            uptime.day - 1, uptime.hour, uptime.minute, uptime.second
        )

    @property
    def current_power_w(self) -> float | None:
        """Return the current power usage in W."""
        if not isinstance(self.wemo, Insight):
            return None
        milliwatts = convert(self.wemo.insight_params.get("currentpower"), float, 0.0)
        assert isinstance(milliwatts, float)
        return milliwatts / 1000.0

    @property
    def today_energy_kwh(self) -> float | None:
        """Return the today total energy usage in kWh."""
        if not isinstance(self.wemo, Insight):
            return None
        milliwatt_seconds = convert(self.wemo.insight_params.get("todaymw"), float, 0.0)
        assert isinstance(milliwatt_seconds, float)
        return round(milliwatt_seconds / (1000.0 * 1000.0 * 60), 2)

    @property
    def detail_state(self) -> str:
        """Return the state of the device."""
        if isinstance(self.wemo, CoffeeMaker):
            return cast(str, self.wemo.mode_string)
        if isinstance(self.wemo, Insight):
            standby_state = int(self.wemo.insight_params.get("state", 0))
            if standby_state == WEMO_ON:
                return STATE_ON
            if standby_state == WEMO_OFF:
                return STATE_OFF
            if standby_state == WEMO_STANDBY:
                return STATE_STANDBY
            return STATE_UNKNOWN
        assert False  # Unreachable code statement.

    @property
    def icon(self) -> str | None:
        """Return the icon of device based on its type."""
        if isinstance(self.wemo, CoffeeMaker):
            return "mdi:coffee"
        return None

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        with self._wemo_call_wrapper("turn on"):
            self.wemo.on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        with self._wemo_call_wrapper("turn off"):
            self.wemo.off()
