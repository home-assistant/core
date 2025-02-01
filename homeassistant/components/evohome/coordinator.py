"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

import aiohttp
import evohomeasync as ec1
import evohomeasync2 as ec2
from evohomeasync2.const import (
    SZ_GATEWAY_ID,
    SZ_GATEWAY_INFO,
    SZ_GATEWAYS,
    SZ_LOCATION_ID,
    SZ_LOCATION_INFO,
    SZ_TEMPERATURE_CONTROL_SYSTEMS,
    SZ_TIME_ZONE,
    SZ_USE_DAYLIGHT_SAVE_SWITCHING,
)
from evohomeasync2.schemas.typedefs import EvoLocStatusResponseT

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_LOCATION_IDX


class EvoDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for evohome integration/client."""

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

        # These will not be None after _async_setup())
        self.loc: ec2.Location = None  # type: ignore[assignment]
        self.tcs: ec2.ControlSystem = None  # type: ignore[assignment]

        self.data: EvoLocStatusResponseT = None  # type: ignore[assignment]
        self.temps: dict[str, float | None] = {}

    async def async_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup.

        This integration does not yet have config flow, so it is inappropriate to
        invoke `async_config_entry_first_refresh()`.
        """

        if not await self.__wrap_async_setup():
            return

        await self._async_refresh(
            log_failures=False, raise_on_auth_failed=True, raise_on_entry_error=True
        )

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

        await self.client.update(dont_update_status=True)  # only need config for now

        try:
            self.loc = self.client.locations[self.loc_idx]
        except IndexError:
            self.logger.error(
                (
                    "Config error: '%s' = %s, but the valid range is 0-%s. "
                    "Unable to continue. Fix any configuration errors and restart HA"
                ),
                CONF_LOCATION_IDX,
                self.loc_idx,
                len(self.client.locations) - 1,
            )

        self.tcs = self.loc.gateways[0].systems[0]

        if self.logger.isEnabledFor(logging.DEBUG):
            loc_info = {
                SZ_LOCATION_ID: self.loc.id,
                SZ_TIME_ZONE: self.loc.config[SZ_TIME_ZONE],
                SZ_USE_DAYLIGHT_SAVE_SWITCHING: self.loc.config[
                    SZ_USE_DAYLIGHT_SAVE_SWITCHING
                ],
            }
            gwy_info = {
                SZ_GATEWAY_ID: self.loc.gateways[0].id,
                SZ_TEMPERATURE_CONTROL_SYSTEMS: [
                    self.loc.gateways[0].systems[0].config
                ],
            }
            config = {
                SZ_LOCATION_INFO: loc_info,
                SZ_GATEWAYS: [{SZ_GATEWAY_INFO: gwy_info}],
            }
            self.logger.debug("Config = %s", config)

    async def call_client_api(
        self,
        client_api: Awaitable[dict[str, Any] | None],
        update_state: bool = True,
    ) -> dict[str, Any] | None:
        """Call a client API and update the Coordinator state if required."""

        try:
            result = await client_api

        except ec2.ApiRequestFailedError as err:
            self.logger.error(err)
            return None

        if update_state:  # wait a moment for system to quiesce before updating state
            await self.async_request_refresh()  # hass.async_create_task() won't help

        return result

    async def _update_v1_api_temps(self) -> None:
        """Get the latest high-precision temperatures of the default Location."""

        assert self.client_v1 is not None  # mypy check

        try:
            await self.client_v1.update()

        except ec1.BadUserCredentialsError as err:
            self.logger.warning(
                (
                    "Unable to obtain high-precision temperatures. "
                    "The high-precision feature will be disabled until next restart."
                    "Message is: %s"
                ),
                err,
            )
            self.client_v1 = None

        except ec1.EvohomeError as err:
            self.logger.warning(
                (
                    "Unable to obtain the latest high-precision temperatures. "
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
            self.temps = await self.client_v1.location_by_id[
                self.loc.id
            ].get_temperatures(dont_update_status=True)

        self.logger.debug("Status (high-res temps) = %s", self.temps)

    async def _update_v2_api_state(self, *args: Any) -> bool:
        """Get the latest modes, temperatures, setpoints of a Location."""

        try:
            status = await self.loc.update()

        except ec2.ApiRequestFailedError as err:
            if err.status == HTTPStatus.TOO_MANY_REQUESTS:
                self.logger.warning(
                    "The vendor's API rate limit has been exceeded. "  # noqa: G004
                    f"Consider increasing the {CONF_SCAN_INTERVAL}."
                )
            else:
                self.logger.error(err)
            return False

        self.logger.debug("Status = %s", status)
        return True

    async def _async_update_data(self) -> EvoLocStatusResponseT:  # type: ignore[override]
        """Fetch the latest state of an entire TCC Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """

        if await self._update_v2_api_state():
            if self.client_v1:
                await self._update_v1_api_temps()

        return self.loc.status
