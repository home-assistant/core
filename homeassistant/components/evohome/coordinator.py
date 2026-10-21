"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from collections.abc import Awaitable
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import Any, override

import evohomeasync as ec1
import evohomeasync2 as ec2
from evohomeasync2.const import (
    SZ_DHW,
    SZ_GATEWAY_ID,
    SZ_GATEWAY_INFO,
    SZ_GATEWAYS,
    SZ_LOCATION_ID,
    SZ_LOCATION_INFO,
    SZ_TEMPERATURE_CONTROL_SYSTEMS,
    SZ_TIME_ZONE,
    SZ_USE_DAYLIGHT_SAVE_SWITCHING,
    SZ_ZONES,
)
from evohomeasync2.typedefs import EvoLocStatusT, EvoTcsConfigResponseT

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SCHEDULE_MAX_AGE


class EvoDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for evohome integration/client."""

    # These will not be None after _async_setup())
    loc: ec2.Location
    tcs: ec2.ControlSystem

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        client_v2: ec2.EvohomeClient,
        *,
        name: str,
        update_interval: timedelta,
        location_idx: int,
        client_v1: ec1.EvohomeClient | None = None,
    ) -> None:
        """Class to manage fetching data."""

        super().__init__(
            hass,
            logger,
            config_entry=None,
            name=name,
            update_interval=update_interval,
        )

        self.client = client_v2
        self.client_v1 = client_v1

        self.loc_idx = location_idx

        self.data: EvoLocStatusT = None  # type: ignore[assignment]
        self.temps: dict[str, float | None] = {}

        self._first_refresh_done = False  # get schedules only after first refresh
        self._schedules_fetched: dict[str, datetime] = {}  # by DHW/zone id

    # our version of async_config_entry_first_refresh()...
    async def async_first_refresh(self) -> None:
        """Refresh data for the first time when integration is setup.

        This integration does not have config flow, so it is inappropriate to
        invoke `async_config_entry_first_refresh()`.
        """

        # can't replicate `if not await self.__wrap_async_setup():` (is mangled), so...
        if not await self._DataUpdateCoordinator__wrap_async_setup():  # type: ignore[attr-defined]
            return

        await self._async_refresh(
            log_failures=False, raise_on_auth_failed=True, raise_on_entry_error=True
        )

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator.

        Fetch the user information, and the configuration of their locations.
        """

        try:
            await self.client.setup()  # only config for now
        except ec2.EvohomeError as err:
            raise UpdateFailed(err) from err

        try:
            self.loc = self.client.locations[self.loc_idx]
        except IndexError as err:
            raise UpdateFailed(
                f"""
                    Config error: 'location_idx' = {self.loc_idx},
                    but the valid range is 0-{len(self.client.locations) - 1}.
                    Unable to continue. Fix any configuration errors and restart HA
                """
            ) from err

        if (tcs := self.loc.tcs) is None:
            raise UpdateFailed(f"Config error: location {self.loc.id} has no TCS")
        self.tcs = tcs

        if self.logger.isEnabledFor(logging.DEBUG):
            loc_info = {
                SZ_LOCATION_ID: self.loc.id,
                SZ_TIME_ZONE: self.loc.config[SZ_TIME_ZONE],
                SZ_USE_DAYLIGHT_SAVE_SWITCHING: self.loc.config[
                    SZ_USE_DAYLIGHT_SAVE_SWITCHING
                ],
            }
            tcs_info: EvoTcsConfigResponseT = {
                **self.tcs.config,
                SZ_ZONES: [zone.config for zone in self.tcs.zones],
            }
            if self.tcs.hotwater:
                tcs_info[SZ_DHW] = self.tcs.hotwater.config
            gwy_info = {
                SZ_GATEWAY_ID: self.loc.gateways[0].id,
                SZ_TEMPERATURE_CONTROL_SYSTEMS: [tcs_info],
            }
            config = {
                SZ_LOCATION_INFO: loc_info,
                SZ_GATEWAYS: [{SZ_GATEWAY_INFO: gwy_info}],
            }
            self.logger.debug("Config = %s", [config])

    async def call_client_api[_T](
        self,
        client_api: Awaitable[_T],
        *,
        request_refresh: bool = True,
        raise_on_error: bool = True,
    ) -> _T | None:
        """Call a client API and update the Coordinator state if required.

        If the call fails, raise HomeAssistantError (e.g. for an action), unless
        raise_on_error is False (e.g. for a background GET), when log it and return None.
        """

        try:
            result = await client_api

        except ec2.AuthenticationFailedError:
            raise

        except ec2.ApiCallFailedError as err:
            if not raise_on_error:
                self.logger.warning(err)
                return None
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_call_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        if request_refresh:  # wait a moment for system to quiesce before updating state
            await self.async_request_refresh()  # hass.async_create_task() won't help

        return result

    async def _update_v1_api_temps(self) -> None:
        """Get the latest high-precision temperatures of the default Location."""

        assert self.client_v1 is not None  # mypy check

        try:
            await self.client_v1.get_status()

        except ec1.BadUserCredentialsError as err:
            self.logger.warning(
                (
                    "Unable to obtain high-precision temperatures. "
                    "The feature will be disabled until next restart: %r"
                ),
                err,
            )
            self.client_v1 = None

        except ec1.EvohomeError as err:
            self.logger.warning(
                (
                    "Unable to obtain the latest high-precision temperatures. "
                    "They will be ignored this refresh cycle: %r"
                ),
                err,
            )
            self.temps = {}  # high-precision temps now considered stale

        else:
            tcs = self.client_v1.location_by_id[self.loc.id].tcs
            self.temps = (
                await tcs.get_temperatures(dont_update_status=True) if tcs else {}
            )

        self.logger.debug("Status (high-res temps) = %s", self.temps)

    async def _update_v2_api_state(self, *args: Any) -> None:
        """Get the latest modes, temperatures, setpoints of a Location."""

        try:
            status = await self.loc.get_status()

        except ec2.ApiCallFailedError as err:
            if err.status != HTTPStatus.TOO_MANY_REQUESTS:
                raise UpdateFailed(err) from err

            raise UpdateFailed(
                f"""
                    The vendor's API rate limit has been exceeded.
                    Consider increasing the {CONF_SCAN_INTERVAL}
                """
            ) from err

        except ec2.EvohomeError as err:
            raise UpdateFailed(err) from err

        self.logger.debug("Status = %s", status)

    def _schedule_is_stale(self, child: ec2.HotWater | ec2.Zone) -> bool:
        """Return True if the schedule has not been fetched within SCHEDULE_MAX_AGE."""
        fetched = self._schedules_fetched.get(child.id)
        return fetched is None or dt_util.utcnow() - fetched >= SCHEDULE_MAX_AGE

    async def _update_v2_schedules(self) -> None:
        for zone in self.tcs.zones:
            if not self._schedule_is_stale(zone):
                continue
            try:
                schedule = await self.call_client_api(
                    zone.get_schedule(), request_refresh=False, raise_on_error=False
                )
            except ec2.InvalidScheduleError as err:
                self.logger.warning(
                    "Zone '%s' has an invalid/missing schedule: %r", zone.name, err
                )
            else:
                if schedule is None:  # the GET failed, so retry it at the next poll
                    continue
            self._schedules_fetched[zone.id] = dt_util.utcnow()

        if (dhw := self.tcs.hotwater) and self._schedule_is_stale(dhw):
            try:
                dhw_schedule = await self.call_client_api(
                    dhw.get_schedule(), request_refresh=False, raise_on_error=False
                )
            except ec2.InvalidScheduleError as err:
                self.logger.warning("DHW has an invalid/missing schedule: %r", err)
            else:
                if dhw_schedule is None:  # the GET failed, so retry it at the next poll
                    return
            self._schedules_fetched[dhw.id] = dt_util.utcnow()

    @override
    async def _async_update_data(self) -> EvoLocStatusT:  # type: ignore[override]
        """Fetch the latest state of an entire TCC Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """

        await self._update_v2_api_state()  # may raise UpdateFailed
        if self.client_v1:
            await self._update_v1_api_temps()  # will never raise UpdateFailed

        # to speed up HA startup, don't update entity schedules during initial
        # async_first_refresh(), only during subsequent async_refresh()...
        if self._first_refresh_done:
            await self._update_v2_schedules()
        else:
            self._first_refresh_done = True

        return self.loc.status
