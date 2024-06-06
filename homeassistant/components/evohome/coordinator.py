"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import timedelta
import logging
from typing import Any

import evohomeasync as ev1
from evohomeasync.schema import SZ_ID, SZ_SESSION_ID, SZ_TEMP
import evohomeasync2 as evo

from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ACCESS_TOKEN,
    ACCESS_TOKEN_EXPIRES,
    CONF_LOCATION_IDX,
    DOMAIN,
    GWS,
    REFRESH_TOKEN,
    TCS,
    USER_DATA,
    UTC_OFFSET,
)
from .helpers import dt_local_to_aware, handle_evo_exception

_LOGGER = logging.getLogger(__name__.rpartition(".")[0])


class EvoBroker:
    """Container for evohome client and data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: evo.EvohomeClient,
        client_v1: ev1.EvohomeClient | None,
        store: Store[dict[str, Any]],
        params: ConfigType,
    ) -> None:
        """Initialize the evohome client and its data structure."""
        self.hass = hass
        self.client = client
        self.client_v1 = client_v1
        self._store = store
        self.params = params

        loc_idx = params[CONF_LOCATION_IDX]
        self._location: evo.Location = client.locations[loc_idx]

        assert isinstance(client.installation_info, list)  # mypy

        self.config = client.installation_info[loc_idx][GWS][0][TCS][0]
        self.tcs: evo.ControlSystem = self._location._gateways[0]._control_systems[0]  # noqa: SLF001
        self.loc_utc_offset = timedelta(minutes=self._location.timeZone[UTC_OFFSET])
        self.temps: dict[str, float | None] = {}

    async def save_auth_tokens(self) -> None:
        """Save access tokens and session IDs to the store for later use."""
        # evohomeasync2 uses naive/local datetimes
        access_token_expires = dt_local_to_aware(
            self.client.access_token_expires  # type: ignore[arg-type]
        )

        app_storage: dict[str, Any] = {
            CONF_USERNAME: self.client.username,
            REFRESH_TOKEN: self.client.refresh_token,
            ACCESS_TOKEN: self.client.access_token,
            ACCESS_TOKEN_EXPIRES: access_token_expires.isoformat(),
        }

        if self.client_v1:
            app_storage[USER_DATA] = {
                SZ_SESSION_ID: self.client_v1.broker.session_id,
            }  # this is the schema for STORAGE_VER == 1
        else:
            app_storage[USER_DATA] = {}

        await self._store.async_save(app_storage)

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

        def get_session_id(client_v1: ev1.EvohomeClient) -> str | None:
            user_data = client_v1.user_data if client_v1 else None
            return user_data.get(SZ_SESSION_ID) if user_data else None  # type: ignore[return-value]

        session_id = get_session_id(self.client_v1)

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
            if str(self.client_v1.location_id) != self._location.locationId:
                _LOGGER.warning(
                    "The v2 API's configured location doesn't match "
                    "the v1 API's default location (there is more than one location), "
                    "so the high-precision feature will be disabled until next restart"
                )
                self.client_v1 = None
            else:
                self.temps = {str(i[SZ_ID]): i[SZ_TEMP] for i in temps}

        finally:
            if self.client_v1 and session_id != self.client_v1.broker.session_id:
                await self.save_auth_tokens()

        _LOGGER.debug("Temperatures = %s", self.temps)

    async def _update_v2_api_state(self, *args: Any) -> None:
        """Get the latest modes, temperatures, setpoints of a Location."""

        access_token = self.client.access_token  # maybe receive a new token?

        try:
            status = await self._location.refresh_status()
        except evo.RequestFailed as err:
            handle_evo_exception(err)
        else:
            async_dispatcher_send(self.hass, DOMAIN)
            _LOGGER.debug("Status = %s", status)
        finally:
            if access_token != self.client.access_token:
                await self.save_auth_tokens()

    async def async_update(self, *args: Any) -> None:
        """Get the latest state data of an entire Honeywell TCC Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """
        await self._update_v2_api_state()

        if self.client_v1:
            await self._update_v1_api_temps()
