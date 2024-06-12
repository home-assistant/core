"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import timedelta
import logging
from typing import Any

import evohomeasync as ev1
from evohomeasync.schema import SZ_ID, SZ_SESSION_ID, SZ_TEMP
import evohomeasync2 as evo
from evohomeasync2.schema.const import (
    SZ_GATEWAY_ID,
    SZ_GATEWAY_INFO,
    SZ_LOCATION_ID,
    SZ_LOCATION_INFO,
    SZ_TIME_ZONE,
)

from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util

from .const import (
    ACCESS_TOKEN,
    ACCESS_TOKEN_EXPIRES,
    CONF_LOCATION_IDX,
    DOMAIN,
    GWS,
    REFRESH_TOKEN,
    STORAGE_KEY,
    STORAGE_VER,
    TCS,
    USER_DATA,
    UTC_OFFSET,
)
from .helpers import dt_aware_to_naive, dt_local_to_aware, handle_evo_exception

_LOGGER = logging.getLogger(__name__.rpartition(".")[0])


class EvoBroker:
    """Broker for evohome client and data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the evohome broker and its data structure."""

        self.hass = hass

        self._session = async_get_clientsession(hass)
        self._store = Store[dict[str, Any]](hass, STORAGE_VER, STORAGE_KEY)

        # the main client, which uses the newer API
        self.client: evo.EvohomeClient = None  # type: ignore[assignment]
        self._tokens: dict[str, Any] = {}

        self.loc_idx: int = None  # type: ignore[assignment]
        self.loc: evo.Location = None  # type: ignore[assignment]

        self.loc_utc_offset: timedelta = None  # type: ignore[assignment]
        self.tcs: evo.ControlSystem = None  # type: ignore[assignment]

        # the older client can be used to obtain high-precision temps (only)
        self.client_v1: ev1.EvohomeClient | None = None
        self._session_id: str | None = None

        self.temps: dict[str, float | None] = {}

    async def authenticate(self, username: str, password: str) -> bool:
        """Check the user credentials against the web API."""

        if (
            self.client is None
            or username != self.client.username
            or password != self.client.password
        ):
            await self._load_auth_tokens(username)  # for self._tokens

            self.client = evo.EvohomeClient(
                username,
                password,
                **self._tokens,
                session=self._session,
            )

        else:  # force a re-authentication
            self.client._user_account = {}  # noqa: SLF001

        try:
            await self.client.login()
        except evo.AuthenticationFailed as err:
            handle_evo_exception(err)
            return False

        self.client_v1 = ev1.EvohomeClient(
            self.client.username,
            self.client.password,
            session_id=self._session_id,
            session=self._session,
        )

        await self._save_auth_tokens()
        return True

    async def _load_auth_tokens(self, username: str) -> None:
        """Load access tokens and session_id from the store and validate them.

        Sets self._tokens and self._session_id to the latest values.
        """

        app_storage: dict[str, Any] = dict(await self._store.async_load() or {})

        if app_storage.pop(CONF_USERNAME, None) != username:
            # any tokens won't be valid, and store might be corrupt
            await self._store.async_save({})

            self._session_id = None
            self._tokens = {}

            return

        # evohomeasync2 requires naive/local datetimes as strings
        if app_storage.get(ACCESS_TOKEN_EXPIRES) is not None and (
            expires := dt_util.parse_datetime(app_storage[ACCESS_TOKEN_EXPIRES])
        ):
            app_storage[ACCESS_TOKEN_EXPIRES] = dt_aware_to_naive(expires)

        user_data: dict[str, str] = app_storage.pop(USER_DATA, {})

        self._session_id = user_data.get(SZ_SESSION_ID)
        self._tokens = app_storage

    async def _save_auth_tokens(self) -> None:
        """Save access tokens and session_id to the store.

        Sets self._tokens and self._session_id to the latest values.
        """

        # evohomeasync2 uses naive/local datetimes
        access_token_expires = dt_local_to_aware(
            self.client.access_token_expires  # type: ignore[arg-type]
        )

        self._tokens = {
            CONF_USERNAME: self.client.username,
            REFRESH_TOKEN: self.client.refresh_token,
            ACCESS_TOKEN: self.client.access_token,
            ACCESS_TOKEN_EXPIRES: access_token_expires.isoformat(),
        }

        self._session_id = self.client_v1.broker.session_id if self.client_v1 else None

        app_storage = self._tokens
        if self.client_v1:
            app_storage[USER_DATA] = {SZ_SESSION_ID: self._session_id}

        await self._store.async_save(app_storage)

    def validate_location(self, loc_idx: int) -> bool:
        """Get the default TCS of the specified location."""

        self.loc_idx = loc_idx

        assert isinstance(self.client.installation_info, list)  # mypy

        try:
            loc_config = self.client.installation_info[loc_idx]
        except IndexError:
            _LOGGER.error(
                (
                    "Config error: '%s' = %s, but the valid range is 0-%s. "
                    "Unable to continue. Fix any configuration errors and restart HA"
                ),
                CONF_LOCATION_IDX,
                loc_idx,
                len(self.client.installation_info) - 1,
            )
            return False

        self.loc = self.client.locations[loc_idx]
        self.loc_utc_offset = timedelta(minutes=self.loc.timeZone[UTC_OFFSET])
        self.tcs = self.loc._gateways[0]._control_systems[0]  # noqa: SLF001

        if _LOGGER.isEnabledFor(logging.DEBUG):
            loc_info = {
                SZ_LOCATION_ID: loc_config[SZ_LOCATION_INFO][SZ_LOCATION_ID],
                SZ_TIME_ZONE: loc_config[SZ_LOCATION_INFO][SZ_TIME_ZONE],
            }
            gwy_info = {
                SZ_GATEWAY_ID: loc_config[GWS][0][SZ_GATEWAY_INFO][SZ_GATEWAY_ID],
                TCS: loc_config[GWS][0][TCS],
            }
            config = {
                SZ_LOCATION_INFO: loc_info,
                GWS: [{SZ_GATEWAY_INFO: gwy_info}],
            }
            _LOGGER.debug("Config = %s", config)

        return True

    async def call_client_api(
        self,
        client_api: Awaitable[dict[str, Any] | None],
        update_state: bool = True,
    ) -> dict[str, Any] | None:
        """Call a client API and update the broker state if required."""

        try:
            result = await client_api
        except evo.RequestFailed as err:
            handle_evo_exception(err)
            return None

        if update_state:  # wait a moment for system to quiesce before updating state
            async_call_later(self.hass, 1, self._update_v2_api_state)

        return result

    async def _update_v1_api_temps(self) -> None:
        """Get the latest high-precision temperatures of the default Location."""

        assert self.client_v1 is not None  # mypy check

        old_session_id = self._session_id

        try:
            temps = await self.client_v1.get_temperatures()

        except ev1.InvalidSchema as err:
            _LOGGER.warning(
                (
                    "Unable to obtain high-precision temperatures. "
                    "It appears the JSON schema is not as expected, "
                    "so the high-precision feature will be disabled until next restart."
                    "Message is: %s"
                ),
                err,
            )
            self.client_v1 = None

        except ev1.RequestFailed as err:
            _LOGGER.warning(
                (
                    "Unable to obtain the latest high-precision temperatures. "
                    "Check your network and the vendor's service status page. "
                    "Proceeding without high-precision temperatures for now. "
                    "Message is: %s"
                ),
                err,
            )
            self.temps = {}  # high-precision temps now considered stale

        except Exception:
            self.temps = {}  # high-precision temps now considered stale
            raise

        else:
            if str(self.client_v1.location_id) != self.loc.locationId:
                _LOGGER.warning(
                    "The v2 API's configured location doesn't match "
                    "the v1 API's default location (there is more than one location), "
                    "so the high-precision feature will be disabled until next restart"
                )
                self.client_v1 = None
            else:
                self.temps = {str(i[SZ_ID]): i[SZ_TEMP] for i in temps}

        finally:
            if self.client_v1 and self.client_v1.broker.session_id != old_session_id:
                await self._save_auth_tokens()

        _LOGGER.debug("Temperatures = %s", self.temps)

    async def _update_v2_api_state(self, *args: Any) -> None:
        """Get the latest modes, temperatures, setpoints of a Location."""

        access_token = self.client.access_token  # maybe receive a new token?

        try:
            status = await self.loc.refresh_status()
        except evo.RequestFailed as err:
            handle_evo_exception(err)
        else:
            async_dispatcher_send(self.hass, DOMAIN)
            _LOGGER.debug("Status = %s", status)
        finally:
            if access_token != self.client.access_token:
                await self._save_auth_tokens()

    async def async_update(self, *args: Any) -> None:
        """Get the latest state data of an entire Honeywell TCC Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """
        await self._update_v2_api_state()

        if self.client_v1:
            await self._update_v1_api_temps()
