"""Support for (EMEA/EU-based) Honeywell TCC climate systems.

Coordinator object for evohome integration.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import Any

import aiohttp.client_exceptions
import evohomeasync
import evohomeasync2

from homeassistant.const import CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import CONF_LOCATION_IDX, DOMAIN, GWS, TCS, UTC_OFFSET

ACCESS_TOKEN = "access_token"
ACCESS_TOKEN_EXPIRES = "access_token_expires"
REFRESH_TOKEN = "refresh_token"
USER_DATA = "user_data"

_LOGGER = logging.getLogger(__name__)


def _handle_exception(err) -> None:
    """Return False if the exception can't be ignored."""
    try:
        raise err

    except evohomeasync2.AuthenticationError:
        _LOGGER.error(
            "Failed to authenticate with the vendor's server. "
            "Check your username and password. NB: Some special password characters "
            "that work correctly via the website will not work via the web API. "
            "Message is: %s",
            err,
        )

    except aiohttp.ClientConnectionError:
        # this appears to be a common occurrence with the vendor's servers
        _LOGGER.warning(
            "Unable to connect with the vendor's server. "
            "Check your network and the vendor's service status page. "
            "Message is: %s",
            err,
        )

    except aiohttp.ClientResponseError:
        if err.status == HTTPStatus.SERVICE_UNAVAILABLE:
            _LOGGER.warning(
                "The vendor says their server is currently unavailable. "
                "Check the vendor's service status page"
            )

        elif err.status == HTTPStatus.TOO_MANY_REQUESTS:
            _LOGGER.warning(
                "The vendor's API rate limit has been exceeded. "
                "If this message persists, consider increasing the %s",
                CONF_SCAN_INTERVAL,
            )

        else:
            raise  # we don't expect/handle any other Exceptions


def _dt_aware_to_naive(dt_aware: datetime) -> datetime:
    dt_naive = datetime.now() + (dt_aware - dt_util.now())
    if dt_naive.microsecond >= 500000:
        dt_naive += timedelta(seconds=1)
    return dt_naive.replace(microsecond=0)


def _dt_local_to_aware(dt_naive: datetime) -> datetime:
    dt_aware = dt_util.now() + (dt_naive - datetime.now())
    if dt_aware.microsecond >= 500000:
        dt_aware += timedelta(seconds=1)
    return dt_aware.replace(microsecond=0)


class EvoDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching data from single endpoint for evohome."""

    pass  # pylint: disable=unnecessary-pass


class EvoBroker:
    """Container for evohome client and data."""

    def __init__(
        self,
        hass,
        client: evohomeasync2.EvohomeClient,
        client_v1: evohomeasync.EvohomeClient | None,
        store: Store[dict[str, Any]],
        params,
    ) -> None:
        """Initialize the evohome client and its data structure."""

        self.hass = hass
        self.client = client
        self.client_v1 = client_v1
        self._store = store
        self.params = params

        loc_idx = params[CONF_LOCATION_IDX]
        self.config = client.installation_info[loc_idx][GWS][0][TCS][0]
        self.tcs = client.locations[loc_idx]._gateways[0]._control_systems[0]
        self.tcs_utc_offset = timedelta(
            minutes=client.locations[loc_idx].timeZone[UTC_OFFSET]
        )
        self.temps: dict[str, Any] | None = {}

    async def load_auth_tokens(self) -> tuple[dict, dict | None]:
        """Load access tokens and session IDs from the store.

        Using these will avoid exceeding the vendor's API rate limits.
        """
        return await self._load_auth_tokens(self._store, self.params)

    @staticmethod
    async def _load_auth_tokens(store, params) -> tuple[dict, dict | None]:
        app_storage = await store.async_load()
        tokens = dict(app_storage or {})

        if tokens.pop(CONF_USERNAME, None) != params[CONF_USERNAME]:
            # any tokens won't be valid, and store might be be corrupt
            await store.async_save({})
            return ({}, None)

        # evohomeasync2 requires naive/local datetimes as strings
        if tokens.get(ACCESS_TOKEN_EXPIRES) is not None and (
            expires := dt_util.parse_datetime(tokens[ACCESS_TOKEN_EXPIRES])
        ):
            tokens[ACCESS_TOKEN_EXPIRES] = _dt_aware_to_naive(expires)

        user_data = tokens.pop(USER_DATA, None)
        return (tokens, user_data)

    async def save_auth_tokens(self) -> None:
        """Save access tokens and session IDs to the store for later use."""
        # evohomeasync2 uses naive/local datetimes
        access_token_expires = _dt_local_to_aware(self.client.access_token_expires)

        app_storage = {
            CONF_USERNAME: self.client.username,
            REFRESH_TOKEN: self.client.refresh_token,
            ACCESS_TOKEN: self.client.access_token,
            ACCESS_TOKEN_EXPIRES: access_token_expires.isoformat(),
        }

        if self.client_v1 and self.client_v1.user_data:
            app_storage[USER_DATA] = {
                "userInfo": {"userID": self.client_v1.user_data["userInfo"]["userID"]},
                "sessionId": self.client_v1.user_data["sessionId"],
            }
        else:
            app_storage[USER_DATA] = None

        await self._store.async_save(app_storage)

    async def call_client_api(self, api_function, update_state=True) -> Any:
        """Call a client API and update the broker state if required."""
        try:
            result = await api_function
        except (aiohttp.ClientError, evohomeasync2.AuthenticationError) as err:
            _handle_exception(err)
            return

        if update_state:  # wait a moment for system to quiesce before updating state
            async_call_later(self.hass, 1, self._update_v2_api_state)

        return result

    async def _update_v1_api_temps(self, *args, **kwargs) -> None:
        """Get the latest high-precision temperatures of the default Location."""

        assert self.client_v1

        def get_session_id(client_v1) -> str | None:
            user_data = client_v1.user_data if client_v1 else None
            return user_data.get("sessionId") if user_data else None

        session_id = get_session_id(self.client_v1)

        try:
            temps = list(await self.client_v1.temperatures(force_refresh=True))

        except aiohttp.ClientError as err:
            _LOGGER.warning(
                "Unable to obtain the latest high-precision temperatures. "
                "Check your network and the vendor's service status page. "
                "Proceeding with low-precision temperatures. "
                "Message is: %s",
                err,
            )
            self.temps = None  # these are now stale, will fall back to v2 temps

        else:
            if (
                str(self.client_v1.location_id)
                != self.client.locations[self.params[CONF_LOCATION_IDX]].locationId
            ):
                _LOGGER.warning(
                    "The v2 API's configured location doesn't match "
                    "the v1 API's default location (there is more than one location), "
                    "so the high-precision feature will be disabled"
                )
                self.client_v1 = self.temps = None
            else:
                self.temps = {str(i["id"]): i["temp"] for i in temps}

        _LOGGER.debug("Temperatures = %s", self.temps)

        if session_id != get_session_id(self.client_v1):
            await self.save_auth_tokens()

    async def _update_v2_api_state(self, *args, **kwargs) -> None:
        """Get the latest modes, temperatures, setpoints of a Location."""
        access_token = self.client.access_token

        loc_idx = self.params[CONF_LOCATION_IDX]
        try:
            status = await self.client.locations[loc_idx].status()
        except aiohttp.ClientError as err:
            _handle_exception(err)
            # raise
        except evohomeasync2.AuthenticationError as err:
            _handle_exception(err)
            # raise UpdateFailed
        else:
            async_dispatcher_send(self.hass, DOMAIN)

            _LOGGER.debug("Status = %s", status)

        if access_token != self.client.access_token:
            await self.save_auth_tokens()

    async def async_update(self, *args, **kwargs) -> None:
        """Get the latest state data of an entire Honeywell TCC Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """
        if self.client_v1:
            await self._update_v1_api_temps()

        await self._update_v2_api_state()
