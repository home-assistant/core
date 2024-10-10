"""DataUpdateCoordinator for the wallbox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from http import HTTPStatus
import logging
from typing import Any, Concatenate

import requests
from wallbox import Wallbox

from homeassistant.components.calendar import CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CHARGER_CURRENCY_KEY,
    CHARGER_DATA_KEY,
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_FEATURES_KEY,
    CHARGER_LAST_EVENT,
    CHARGER_LOCKED_UNLOCKED_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_MAX_ICP_CURRENT_KEY,
    CHARGER_PLAN_KEY,
    CHARGER_POWER_BOOST_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_STATUS_DESCRIPTION_KEY,
    CHARGER_STATUS_ID_KEY,
    CODE_KEY,
    DOMAIN,
    UPDATE_INTERVAL,
    ChargerStatus,
)

_LOGGER = logging.getLogger(__name__)

# Translation of StatusId based on Wallbox portal code:
# https://my.wallbox.com/src/utilities/charger/chargerStatuses.js
CHARGER_STATUS: dict[int, ChargerStatus] = {
    0: ChargerStatus.DISCONNECTED,
    14: ChargerStatus.ERROR,
    15: ChargerStatus.ERROR,
    161: ChargerStatus.READY,
    162: ChargerStatus.READY,
    163: ChargerStatus.DISCONNECTED,
    164: ChargerStatus.WAITING,
    165: ChargerStatus.LOCKED,
    166: ChargerStatus.UPDATING,
    177: ChargerStatus.SCHEDULED,
    178: ChargerStatus.PAUSED,
    179: ChargerStatus.SCHEDULED,
    180: ChargerStatus.WAITING_FOR_CAR,
    181: ChargerStatus.WAITING_FOR_CAR,
    182: ChargerStatus.PAUSED,
    183: ChargerStatus.WAITING_IN_QUEUE_POWER_SHARING,
    184: ChargerStatus.WAITING_IN_QUEUE_POWER_SHARING,
    185: ChargerStatus.WAITING_IN_QUEUE_POWER_BOOST,
    186: ChargerStatus.WAITING_IN_QUEUE_POWER_BOOST,
    187: ChargerStatus.WAITING_MID_FAILED,
    188: ChargerStatus.WAITING_MID_SAFETY,
    189: ChargerStatus.WAITING_IN_QUEUE_ECO_SMART,
    193: ChargerStatus.CHARGING,
    194: ChargerStatus.CHARGING,
    195: ChargerStatus.CHARGING,
    196: ChargerStatus.DISCHARGING,
    209: ChargerStatus.LOCKED,
    210: ChargerStatus.LOCKED_CAR_CONNECTED,
}


@dataclass
class WallboxEventMixIn:
    """Mixin for Wallbox calendar event."""

    charger_name: str
    username: str
    session_id: str
    currency: str
    session_type: str
    serial_number: int
    energy: float
    mid_energy: float
    cost_kw: float
    session_cost: float


@dataclass
class WallboxEvent(CalendarEvent, WallboxEventMixIn):
    """A class to describe a Wallbox calendar event."""


def _require_authentication[_WallboxCoordinatorT: WallboxCoordinator, **_P](
    func: Callable[Concatenate[_WallboxCoordinatorT, _P], Any],
) -> Callable[Concatenate[_WallboxCoordinatorT, _P], Any]:
    """Authenticate with decorator using Wallbox API."""

    def require_authentication(
        self: _WallboxCoordinatorT, *args: _P.args, **kwargs: _P.kwargs
    ) -> Any:
        """Authenticate using Wallbox API."""
        try:
            self.authenticate()
            return func(self, *args, **kwargs)
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == HTTPStatus.FORBIDDEN:
                raise ConfigEntryAuthFailed from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error

    return require_authentication


class WallboxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Wallbox Coordinator class."""

    def __init__(self, station: str, wallbox: Wallbox, hass: HomeAssistant) -> None:
        """Initialize."""
        self._station = station
        self._wallbox = wallbox

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=datetime.timedelta(seconds=UPDATE_INTERVAL),
        )

    def authenticate(self) -> None:
        """Authenticate using Wallbox API."""
        self._wallbox.authenticate()

    def _validate(self) -> None:
        """Authenticate using Wallbox API."""
        try:
            self._wallbox.authenticate()
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InvalidAuth from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error

    async def async_validate_input(self) -> None:
        """Get new sensor data for Wallbox component."""
        await self.hass.async_add_executor_job(self._validate)

    @_require_authentication
    def _get_data(self) -> dict[str, Any]:
        """Get new sensor data for Wallbox component."""
        data: dict[str, Any] = self._wallbox.getChargerStatus(self._station)
        data[CHARGER_MAX_CHARGING_CURRENT_KEY] = data[CHARGER_DATA_KEY][
            CHARGER_MAX_CHARGING_CURRENT_KEY
        ]
        data[CHARGER_LOCKED_UNLOCKED_KEY] = data[CHARGER_DATA_KEY][
            CHARGER_LOCKED_UNLOCKED_KEY
        ]
        data[CHARGER_ENERGY_PRICE_KEY] = data[CHARGER_DATA_KEY][
            CHARGER_ENERGY_PRICE_KEY
        ]
        # Only show max_icp_current if power_boost is available in the wallbox unit:
        if (
            data[CHARGER_DATA_KEY].get(CHARGER_MAX_ICP_CURRENT_KEY, 0) > 0
            and CHARGER_POWER_BOOST_KEY
            in data[CHARGER_DATA_KEY][CHARGER_PLAN_KEY][CHARGER_FEATURES_KEY]
        ):
            data[CHARGER_MAX_ICP_CURRENT_KEY] = data[CHARGER_DATA_KEY][
                CHARGER_MAX_ICP_CURRENT_KEY
            ]

        data[CHARGER_CURRENCY_KEY] = (
            f"{data[CHARGER_DATA_KEY][CHARGER_CURRENCY_KEY][CODE_KEY]}/kWh"
        )

        data[CHARGER_STATUS_DESCRIPTION_KEY] = CHARGER_STATUS.get(
            data[CHARGER_STATUS_ID_KEY], ChargerStatus.UNKNOWN
        )

        events = self._get_sessions(
            data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY],
            dt_util.now() - datetime.timedelta(days=30),
            dt_util.now(),
        )
        data[CHARGER_LAST_EVENT] = events[0] if len(events) > 0 else None
        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Get new sensor data for Wallbox component."""
        return await self.hass.async_add_executor_job(self._get_data)

    @_require_authentication
    def _set_charging_current(self, charging_current: float) -> None:
        """Set maximum charging current for Wallbox."""
        try:
            self._wallbox.setMaxChargingCurrent(self._station, charging_current)
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InvalidAuth from wallbox_connection_error
            raise

    async def async_set_charging_current(self, charging_current: float) -> None:
        """Set maximum charging current for Wallbox."""
        await self.hass.async_add_executor_job(
            self._set_charging_current, charging_current
        )
        await self.async_request_refresh()

    @_require_authentication
    def _get_sessions(
        self,
        charger_id: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[WallboxEvent]:
        """Get charging sessions between timestamps for Wallbox."""
        data = self._wallbox.getSessionList(charger_id, start_date, end_date)
        events: list[WallboxEvent] = []

        tzone = dt_util.get_default_time_zone()
        for event in data["data"]:
            if event["type"] == "charger_charging_session":
                events.append(
                    WallboxEvent(
                        charger_name=event["attributes"]["charger_name"],
                        username=event["attributes"]["user_name"],
                        session_id=event["attributes"]["id"],
                        currency=event["attributes"]["currency_code"],
                        session_type=event["attributes"]["session_type"],
                        serial_number=event["attributes"]["charger_id"],
                        energy=event["attributes"]["energy"],
                        mid_energy=event["attributes"]["mid_energy"],
                        cost_kw=event["attributes"]["energy_price"],
                        session_cost=event["attributes"]["total_cost"],
                        start=datetime.datetime.fromtimestamp(
                            event["attributes"]["start_time"], tzone
                        ),
                        end=datetime.datetime.fromtimestamp(
                            event["attributes"]["end_time"], tzone
                        ),
                        summary=f"Charger {event["attributes"]["charger_name"]}: {event["attributes"]["energy"]}KWh",
                    )
                )
            elif event["type"] == "charger_log_session":
                events.append(
                    WallboxEvent(
                        charger_name=event["attributes"]["charger_name"],
                        username=event["attributes"]["user_name"],
                        session_id=event["id"],
                        currency=event["attributes"]["currency"]["code"],
                        session_type="",
                        serial_number=event["attributes"]["charger"],
                        energy=event["attributes"]["energy"],
                        mid_energy=event["attributes"]["mid_energy"],
                        cost_kw=0,
                        session_cost=event["attributes"]["cost"],
                        start=datetime.datetime.fromtimestamp(
                            event["attributes"]["start"], tzone
                        ),
                        end=datetime.datetime.fromtimestamp(
                            event["attributes"]["end"], tzone
                        ),
                        summary=f"Charger {event["attributes"]["charger_name"]}: {event["attributes"]["energy"]}KWh",
                    )
                )

        return events

    async def async_get_sessions(
        self,
        charger_id: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[WallboxEvent]:
        """Get charging sessions between timestamps for Wallbox."""
        return await self.hass.async_add_executor_job(
            self._get_sessions, charger_id, start_date, end_date
        )

    @_require_authentication
    def _set_icp_current(self, icp_current: float) -> None:
        """Set maximum icp current for Wallbox."""
        try:
            self._wallbox.setIcpMaxCurrent(self._station, icp_current)
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InvalidAuth from wallbox_connection_error
            raise

    async def async_set_icp_current(self, icp_current: float) -> None:
        """Set maximum icp current for Wallbox."""
        await self.hass.async_add_executor_job(self._set_icp_current, icp_current)
        await self.async_request_refresh()

    @_require_authentication
    def _set_energy_cost(self, energy_cost: float) -> None:
        """Set energy cost for Wallbox."""

        self._wallbox.setEnergyCost(self._station, energy_cost)

    async def async_set_energy_cost(self, energy_cost: float) -> None:
        """Set energy cost for Wallbox."""
        await self.hass.async_add_executor_job(self._set_energy_cost, energy_cost)
        await self.async_request_refresh()

    @_require_authentication
    def _set_lock_unlock(self, lock: bool) -> None:
        """Set wallbox to locked or unlocked."""
        try:
            if lock:
                self._wallbox.lockCharger(self._station)
            else:
                self._wallbox.unlockCharger(self._station)
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InvalidAuth from wallbox_connection_error
            raise

    async def async_set_lock_unlock(self, lock: bool) -> None:
        """Set wallbox to locked or unlocked."""
        await self.hass.async_add_executor_job(self._set_lock_unlock, lock)
        await self.async_request_refresh()

    @_require_authentication
    def _pause_charger(self, pause: bool) -> None:
        """Set wallbox to pause or resume."""

        if pause:
            self._wallbox.pauseChargingSession(self._station)
        else:
            self._wallbox.resumeChargingSession(self._station)

    async def async_pause_charger(self, pause: bool) -> None:
        """Set wallbox to pause or resume."""
        await self.hass.async_add_executor_job(self._pause_charger, pause)
        await self.async_request_refresh()


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
