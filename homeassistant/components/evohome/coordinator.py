"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Final, override

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
from evohomeasync2.typedefs import (
    EvoDhwScheduleDayOfWeekT,
    EvoLocStatusT,
    EvoTcsConfigResponseT,
    EvoZonScheduleDayOfWeekT,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SCHEDULE_MAX_AGE
from .helpers import as_camel_case

# any other reason gets "api_request_failed"
_API_CALL_ERROR_TRANSLATION_KEYS: Final[dict[ec2.ApiCallErrorReason, str]] = {
    ec2.ApiCallErrorReason.CONNECTION_FAILED: "api_connection_failed",
    ec2.ApiCallErrorReason.CREDENTIALS_INVALID: "api_credentials_invalid",
    ec2.ApiCallErrorReason.RATE_LIMITED: "api_rate_limited",
    ec2.ApiCallErrorReason.REQUEST_REJECTED: "api_request_rejected",
    ec2.ApiCallErrorReason.SERVER_ERROR: "api_server_error",
}


def _api_call_error_key(err: ec2.ApiCallFailedError) -> str:
    """Return the translation key of a failed API call, by its reason."""
    return _API_CALL_ERROR_TRANSLATION_KEYS.get(err.reason, "api_request_failed")


# a request that the client rejected, before any API call (i.e. invalid arguments)
_REQUEST_ERROR_TRANSLATION_KEYS: Final[dict[ec2.RequestErrorReason, str]] = {
    ec2.RequestErrorReason.MODE_UNKNOWN: "mode_unknown",
    ec2.RequestErrorReason.MODE_UNSUPPORTED: "mode_not_supported",
    ec2.RequestErrorReason.TIMESPAN_NOT_ALLOWED: "mode_cant_be_temporary",
    ec2.RequestErrorReason.TIMESPAN_REQUIRED: "mode_timespan_required",
    ec2.RequestErrorReason.TIMESPAN_NOT_IN_FUTURE: "mode_timespan_not_in_future",
}
_TIMESPAN_UNSUPPORTED_TRANSLATION_KEYS: Final[dict[str, str]] = {
    ec2.TimingMode.DURATION: "mode_cant_have_duration",
    ec2.TimingMode.PERIOD: "mode_cant_have_period",
}


def _bad_request_error(err: ec2.BadApiRequestError) -> ServiceValidationError:
    """Return the translated error of a request that the client has rejected.

    The reason picks the message, and the details supply its placeholders (only the
    mode is used, spelt as the set_system_mode action expects it). A zone/DHW override
    has its own messages, without a placeholder.
    """

    if (mode := err.details.get("mode")) is None:  # e.g. TIMESPAN_CONFLICTING
        return ServiceValidationError(
            translation_domain=DOMAIN, translation_key="request_invalid"
        )

    # a zone/DHW override (DHW uses ZoneMode too); a system mode can't be unknown
    if mode in ec2.ZoneMode and err.reason != ec2.RequestErrorReason.MODE_UNKNOWN:
        return ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=(
                "override_not_in_future"
                if err.reason == ec2.RequestErrorReason.TIMESPAN_NOT_IN_FUTURE
                else "override_request_invalid"
            ),
        )

    if err.reason == ec2.RequestErrorReason.TIMESPAN_UNSUPPORTED:
        key = _TIMESPAN_UNSUPPORTED_TRANSLATION_KEYS.get(
            err.details.get("timing_mode", ""), "mode_request_invalid"
        )
    else:
        key = _REQUEST_ERROR_TRANSLATION_KEYS.get(err.reason, "mode_request_invalid")

    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders={"mode": as_camel_case(mode)},
    )


def _log_api_call_failure(logger: logging.Logger, err: ec2.ApiCallFailedError) -> None:
    """Log (as debug) what the translated error of a failed API call leaves out."""
    logger.debug(
        "The request to the vendor's API failed: %s (reason=%s, status=%s, errors=%s)",
        err,
        err.reason,
        err.status,
        list(err.errors),
    )


def _log_client_error(logger: logging.Logger, err: ec2.EvohomeError) -> None:
    """Log (as debug) what the translated error of a client error leaves out."""
    logger.debug(
        "%s: %s (reason=%s, details=%s)",
        type(err).__name__,
        err,
        err.reason,
        err.details,
    )


type _Schedule = list[EvoDhwScheduleDayOfWeekT] | list[EvoZonScheduleDayOfWeekT]
type _HighPrecisionTemps = dict[str, float | None]  # by DHW/zone id

# keep the last high-precision temps for this many failed polls (i.e. 10 minutes)
_HIGH_PRECISION_MAX_FAILED_POLLS: Final = 2

_ERR_SCHEDULE_UPDATE: Final = (
    "%s: Failed to update the schedule (keeping any previous one): %s"
)


class _EvoCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base for the evohome coordinators (the integration has no config entry)."""

    # our version of async_config_entry_first_refresh()...
    async def async_first_refresh(self) -> None:
        """Refresh data for the first time when integration is setup.

        This integration does not have config flow, so it is inappropriate to
        invoke `async_config_entry_first_refresh()`.
        """

        # can't replicate `if not await self.__wrap_async_setup():` (is mangled), so...
        if not await self._DataUpdateCoordinator__wrap_async_setup():  # type: ignore[attr-defined]
            return

        await self._async_refresh(log_failures=False)


class EvoAccountCoordinator(_EvoCoordinator[_HighPrecisionTemps]):
    """Coordinator for an evohome account (the user's config, high-precision temps).

    Its data is the latest high-precision temperatures, by DHW/zone id. They are
    polled, but are not refreshed on demand (unlike a location). If a poll fails, the
    last temperatures are kept for a grace period, before the zones use their v2 ones.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        client_v2: ec2.EvohomeClient,
        *,
        name: str,
        update_interval: timedelta,
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

        self.data = {}

        self._failed_polls = 0

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator.

        Fetch the user information, and the configuration of their locations.
        """

        try:
            await self.client.setup()  # only config for now

        except ec2.ApiConnectionFailedError as err:
            _log_api_call_failure(self.logger, err)
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN,
                translation_key="api_connection_failed",
            ) from err

        except ec2.ApiCallFailedError as err:
            _log_api_call_failure(self.logger, err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key=_api_call_error_key(err),
                retry_after=err.retry_after,
            ) from err

        except ec2.BadApiResponseError as err:
            _log_client_error(self.logger, err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_response_invalid",
            ) from err

    @override
    async def _async_update_data(self) -> _HighPrecisionTemps:
        """Get the latest high-precision temperatures of the account's locations.

        Never raises UpdateFailed, as the temperatures are optional.
        """

        if self.client_v1 is None:
            return self.data

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
            return {}

        except (ec1.EvohomeError, TimeoutError) as err:
            self._failed_polls += 1
            if self._failed_polls <= _HIGH_PRECISION_MAX_FAILED_POLLS:
                self.logger.debug(
                    "Unable to obtain the latest high-precision temperatures, "
                    "so keeping the previous ones: %r",
                    err,
                )
                return self.data

            if self._failed_polls == _HIGH_PRECISION_MAX_FAILED_POLLS + 1:
                self.logger.warning(
                    (
                        "Unable to obtain the latest high-precision temperatures. "
                        "Standard-precision temperatures will be used until they "
                        "are available again: %r"
                    ),
                    err,
                )
            return {}

        if self._failed_polls > _HIGH_PRECISION_MAX_FAILED_POLLS:
            self.logger.info("High-precision temperatures are available again")
        self._failed_polls = 0

        temps: _HighPrecisionTemps = {}
        for loc in self.client_v1.location_by_id.values():
            if loc.tcs:
                temps |= await loc.tcs.get_temperatures(dont_update_status=True)

        self.logger.debug("Status (high-res temps) = %s", temps)
        return temps


class EvoLocationCoordinator(_EvoCoordinator[EvoLocStatusT]):
    """Coordinator for an evohome location (its status and schedules)."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        account: EvoAccountCoordinator,
        location: ec2.Location,
        *,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Class to manage fetching data."""

        super().__init__(
            hass,
            logger,
            config_entry=None,
            name=name,
            update_interval=update_interval,
        )

        if TYPE_CHECKING:
            assert location.tcs is not None  # the caller skips locations without one

        self.account = account
        self.client = account.client

        self.loc = location
        self.tcs = location.tcs

        self.data: EvoLocStatusT = None  # type: ignore[assignment]

        self._first_refresh_done = False  # get schedules only after first refresh
        self._schedules_fetched: dict[str, datetime] = {}  # by DHW/zone id

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator (log the location's configuration)."""

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
    ) -> _T:
        """Call a client API and update the Coordinator state if required.

        If the call fails, raise HomeAssistantError (ServiceValidationError, if the client
        rejected the request before making it). The client's error is chained to it, and
        logged as debug: it is not logged at a higher level, as HA reports the error.
        """

        try:
            result = await client_api

        except ec2.ApiCallFailedError as err:  # incl. AuthenticationFailedError
            _log_api_call_failure(self.logger, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=_api_call_error_key(err),
            ) from err

        except ec2.BadApiRequestError as err:  # e.g. InvalidSetModeError
            _log_client_error(self.logger, err)
            raise _bad_request_error(err) from err

        if request_refresh:  # wait a moment for system to quiesce before updating state
            await self.async_request_refresh()  # hass.async_create_task() won't help

        return result

    async def _update_v2_api_state(self, *args: Any) -> None:
        """Get the latest modes, temperatures, setpoints of a Location."""

        try:
            status = await self.loc.get_status()

        except ec2.ApiConnectionFailedError as err:
            _log_api_call_failure(self.logger, err)
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN,
                translation_key="api_connection_failed",
            ) from err

        except ec2.ApiCallFailedError as err:
            _log_api_call_failure(self.logger, err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key=_api_call_error_key(err),
                retry_after=err.retry_after,
            ) from err

        except ec2.BadApiResponseError as err:
            _log_client_error(self.logger, err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_response_invalid",
            ) from err

        except ec2.StaleConfigError as err:
            _log_client_error(self.logger, err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="config_stale",
            ) from err

        self.logger.debug("Status = %s", status)

    def _schedule_is_stale(self, child: ec2.HotWater | ec2.Zone) -> bool:
        """Return True if the schedule has not been fetched within SCHEDULE_MAX_AGE."""
        fetched = self._schedules_fetched.get(child.id)
        return fetched is None or dt_util.utcnow() - fetched >= SCHEDULE_MAX_AGE

    async def _update_v2_schedules(self) -> None:
        """Fetch any stale schedules, logging (rather than raising) any failures."""

        children: list[ec2.HotWater | ec2.Zone] = list(self.tcs.zones)
        if self.tcs.hotwater:
            children.append(self.tcs.hotwater)

        for child in children:
            if self._schedule_is_stale(child):
                await self.async_get_schedule(child, raise_on_error=False)

    async def async_ensure_schedule(self, child: ec2.HotWater | ec2.Zone) -> None:
        """Fetch the schedule of a DHW/zone if it is stale, for an action that needs it.

        Raise HomeAssistantError if the GET fails, as the action would.
        """

        if self._schedule_is_stale(child):
            await self.async_get_schedule(child)

    async def async_get_schedule(
        self, child: ec2.HotWater | ec2.Zone, *, raise_on_error: bool = True
    ) -> None:
        """Fetch the schedule of a DHW/zone, recording when it was fetched.

        This is the only place a schedule is fetched. If the GET fails, raise
        HomeAssistantError unless raise_on_error is False, in which case log it and
        don't record the fetch time (so it will be retried). An invalid schedule is
        logged, and is not retried until it is stale. Either way, any previous schedule
        is kept.
        """

        # annotated, as mypy can't infer a type from the HotWater | Zone union
        client_api: Awaitable[_Schedule] = child.get_schedule()
        try:
            schedule = await self.call_client_api(client_api, request_refresh=False)
        except HomeAssistantError as err:
            if raise_on_error:
                raise
            self.logger.warning(_ERR_SCHEDULE_UPDATE, child, err.__cause__ or err)
            return  # the GET failed, so retry it at the next poll
        except ec2.InvalidGetScheduleError as err:
            self.logger.warning(_ERR_SCHEDULE_UPDATE, child, err)
        else:
            self.logger.debug("%s: Schedule = %s", child, schedule)

        self._schedules_fetched[child.id] = dt_util.utcnow()

    @override
    async def _async_update_data(self) -> EvoLocStatusT:
        """Fetch the latest state of an entire TCC Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """

        await self._update_v2_api_state()  # may raise UpdateFailed

        # to speed up HA startup, don't update entity schedules during initial
        # async_first_refresh(), only during subsequent async_refresh()...
        if self._first_refresh_done:
            await self._update_v2_schedules()
        else:
            self._first_refresh_done = True

        return self.loc.status


@dataclass
class EvoData:
    """Dataclass for storing evohome data."""

    account: EvoAccountCoordinator
    locations: list[EvoLocationCoordinator]
