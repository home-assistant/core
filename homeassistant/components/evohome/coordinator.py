"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import timedelta
import logging
from typing import Any

import aiohttp
import evohomeasync as ec1
import evohomeasync2 as ec2
from evohomeasync2.const import (
    SZ_GATEWAY_ID,
    SZ_GATEWAY_INFO,
    SZ_LOCATION_ID,
    SZ_LOCATION_INFO,
    SZ_TIME_ZONE,
)
from evohomeasync2.schemas.typedefs import EvoLocStatusResponseT

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_LOCATION_IDX, DOMAIN, GWS, TCS
from .helpers import handle_evo_exception


class EvoDataUpdateCoordinator(DataUpdateCoordinator):
    """Broker for evohome client broker."""

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

        # self.data: _DataT = None  # type: ignore[assignment]
        self.temps: dict[str, float | None] = {}

        self.loc: ec2.Location | None = None
        self.tcs: ec2.ControlSystem | None = None

    async def async_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup.

        This integration does not yet have config flow, so it is inappropriate to
        invoke `async_config_entry_first_refresh()`.
        """

        if await self.__wrap_async_setup():
            await self._async_refresh(
                log_failures=False, raise_on_auth_failed=True, raise_on_entry_error=True
            )
            if self.last_update_success:
                return

    def _async_unsub_shutdown(self) -> None:
        """Cancel any scheduled call."""
        if self._unsub_shutdown:
            self._unsub_shutdown()
            self._unsub_shutdown = None

    async def __wrap_async_setup(self) -> bool:
        """Error handling for _async_setup."""

        try:
            await self._async_setup()

        except (TimeoutError, aiohttp.ClientError) as err:
            self.last_exception = err

        except ec2.EvohomeError as err:
            self.last_exception = err

        except Exception as err:  # pylint: disable=broad-except
            self.last_exception = err
            self.logger.exception("Unexpected error fetching %s data", self.name)

        else:
            return True

        self.last_update_success = False
        return False

    async def _async_setup(self) -> None:
        """Set up the coordinator (fetch the configuration of a TCC Location)."""

        await self.client.update(_dont_update_status=True)  # only need config

        try:
            self.loc = self.client.locations[self.loc_idx]
        except IndexError as err:
            self.logger.error(
                (
                    "Config error: '%s' = %s, but the valid range is 0-%s. "
                    "Unable to continue. Fix any configuration errors and restart HA"
                ),
                CONF_LOCATION_IDX,
                self.loc_idx,
                len(self.client.locations) - 1,
            )
            raise ValueError("TODO") from err

        self.tcs = self.loc.gateways[0].systems[0]

        if self.logger.isEnabledFor(logging.DEBUG):
            loc_info = {
                SZ_LOCATION_ID: self.loc.locationId,
                SZ_TIME_ZONE: self.loc.time_zone_info,
            }
            gwy_info = {
                SZ_GATEWAY_ID: self.loc.gateways[0].gatewayId,
                TCS: [self.loc.gateways[0].systems[0].config],
            }
            config = {
                SZ_LOCATION_INFO: loc_info,
                GWS: [{SZ_GATEWAY_INFO: gwy_info}],
            }
            self.logger.debug("Config = %s", config)

    async def call_client_api(
        self,
        client_api: Awaitable[dict[str, Any] | None],
        update_state: bool = True,
    ) -> dict[str, Any] | None:
        """Call a client API and update the broker state if required."""

        try:
            result = await client_api

        except ec2.ApiRequestFailedError as err:
            handle_evo_exception(err)
            return None

        if update_state:  # wait a moment for system to quiesce before updating state
            await self.async_refresh()

        return result

    async def _update_v1_api_temps(self) -> None:
        """Get the latest high-precision temperatures of the default Location."""

        assert self.client_v1 is not None  # mypy check

        # try:
        #     temps = await self.client_v1.get_temperatures()

        # except ec1.InvalidSchemaError as err:
        #     self.logger.warning(
        #         (
        #             "Unable to obtain high-precision temperatures. "
        #             "It appears the JSON schema is not as expected, "
        #             "so the high-precision feature will be disabled until next restart."
        #             "Message is: %s"
        #         ),
        #         err,
        #     )
        #     self.client_v1 = None

        # except ec1.ApiRequestFailedError as err:
        #     self.logger.warning(
        #         (
        #             "Unable to obtain the latest high-precision temperatures. "
        #             "Check your network and the vendor's service status page. "
        #             "Proceeding without high-precision temperatures for now. "
        #             "Message is: %s"
        #         ),
        #         err,
        #     )
        #     self.temps = {}  # high-precision temps now considered stale

        # except Exception:
        #     self.temps = {}  # high-precision temps now considered stale
        #     raise

        # else:
        #     if str(self.client_v1.location_id) != self.loc.locationId:
        #         self.logger.warning(
        #             "The v2 API's configured location doesn't match "
        #             "the v1 API's default location (there is more than one location), "
        #             "so the high-precision feature will be disabled until next restart"
        #         )
        #         self.client_v1 = None
        #     else:
        #         self.temps = {str(i[SZ_ID]): i[SZ_TEMP] for i in temps}

        self.logger.debug("Status (high-res temps) = %s", self.temps)

    async def _update_v2_api_state(self, *args: Any) -> None:
        """Get the latest modes, temperatures, setpoints of a Location."""

        assert self.loc is not None  # mypy

        try:
            status = await self.loc.update()

        except ec2.ApiRequestFailedError as err:
            handle_evo_exception(err)

        else:
            async_dispatcher_send(self.hass, DOMAIN)
            self.logger.debug("Status = %s", status)

    async def _async_update_data(self) -> EvoLocStatusResponseT:  # type: ignore[override]
        """Fetch the latest state of an entire TCC Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """

        await self._update_v2_api_state()

        if self.client_v1:
            await self._update_v1_api_temps()

        assert self.loc is not None  # mypy
        return self.loc.status  # type: ignore[return-value]
