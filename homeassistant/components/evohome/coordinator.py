"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

import evohomeasync as ev1
from evohomeasync.schema import SZ_ID, SZ_TEMP
import evohomeasync2 as evo
from evohomeasync2.schema.const import (
    SZ_GATEWAY_ID,
    SZ_GATEWAY_INFO,
    SZ_LOCATION_ID,
    SZ_LOCATION_INFO,
    SZ_TIME_ZONE,
)

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_LOCATION_IDX, DOMAIN, GWS, TCS, UTC_OFFSET
from .helpers import handle_evo_exception

if TYPE_CHECKING:
    from . import EvoSession

_LOGGER = logging.getLogger(__name__.rpartition(".")[0])


class EvoBroker:
    """Broker for evohome client broker."""

    loc_idx: int
    loc: evo.Location
    loc_utc_offset: timedelta
    tcs: evo.ControlSystem

    def __init__(self, sess: EvoSession) -> None:
        """Initialize the evohome broker and its data structure."""

        self._sess = sess
        self.hass = sess.hass

        assert sess.client_v2 is not None  # mypy

        self.client = sess.client_v2
        self.client_v1 = sess.client_v1

        self.temps: dict[str, float | None] = {}

    def validate_location(self, loc_idx: int) -> bool:
        """Get the default TCS of the specified location."""

        self.loc_idx = loc_idx

        assert self.client.installation_info is not None  # mypy

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
            await self.hass.data[DOMAIN]["coordinator"].async_request_refresh()

        return result

    async def _update_v1_api_temps(self) -> None:
        """Get the latest high-precision temperatures of the default Location."""

        assert self.client_v1 is not None  # mypy check

        old_session_id = self._sess.session_id

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
                await self._sess.save_auth_tokens()

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
                await self._sess.save_auth_tokens()

    async def async_update(self, *args: Any) -> None:
        """Get the latest state data of an entire Honeywell TCC Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """
        await self._update_v2_api_state()

        if self.client_v1:
            await self._update_v1_api_temps()
