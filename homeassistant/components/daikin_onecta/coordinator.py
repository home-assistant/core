"""Coordinator for Daikin Onecta integration."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime, time, timedelta, tzinfo
import logging
from math import ceil
import random
from typing import cast, override

from daikin_onecta import Site
from daikin_onecta.client import OnectaClient
from daikin_onecta.exceptions import (
    OnectaApiError,
    OnectaAuthenticationError,
    OnectaConnectionError,
    OnectaRateLimitError,
)
from daikin_onecta.models import GatewayDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANAGEMENT_POINT_DEVICE_NAMES
from .device import DaikinOnectaDevice
from .discovery import gateway_entity_keys

_LOGGER = logging.getLogger(__name__)

_HIGH_SCAN_INTERVAL = timedelta(minutes=10)
_LOW_SCAN_INTERVAL = timedelta(minutes=30)
_HIGH_SCAN_START = time(7)
_LOW_SCAN_START = time(22)
_POST_WRITE_COOLDOWN = timedelta(seconds=30)
_DEFAULT_DAILY_CALL_LIMIT = 200
_POLLING_BUDGET_FRACTION = 0.55
_MINIMUM_POLL_INTERVAL = timedelta(minutes=3)

type DaikinOnectaConfigEntry = ConfigEntry[OnectaDataUpdateCoordinator]


def gateway_site_membership(sites: list[Site], gateway_device_id: str) -> bool | None:
    """Return membership without assuming an incomplete site response is empty."""
    membership = [site.has_gateway_device(gateway_device_id) for site in sites]
    if True in membership:
        return True
    return None if None in membership else False


class OnectaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, DaikinOnectaDevice]]):
    """Class to manage fetching data from the API."""

    config_entry: DaikinOnectaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DaikinOnectaConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ) -> None:
        """Initialize."""
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        self._client = OnectaClient(
            async_get_clientsession(hass), self.async_get_access_token
        )
        self._last_patch_call: datetime | None = None
        self._cloud_lock = asyncio.Lock()
        self._cloud_update_sequence = 0
        self._reload_pending = False

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self._determine_update_interval(),
        )

    @property
    def client(self) -> OnectaClient:
        """Return the underlying Onecta client."""
        return self._client

    @property
    def rate_limits(self) -> dict[str, int | None]:
        """Return rate limits using the existing entity and diagnostics keys."""
        rate_limit = self._client.rate_limit
        return {
            "minute": rate_limit.minute_limit,
            "day": rate_limit.day_limit,
            "remaining_minutes": rate_limit.minute_remaining,
            "remaining_day": rate_limit.day_remaining,
            "retry_after": rate_limit.retry_after,
            "ratelimit_reset": rate_limit.reset,
        }

    @property
    def last_patch_call(self) -> datetime | None:
        """Return when the last successful cloud write completed."""
        return self._last_patch_call

    async def async_get_access_token(self) -> str:
        """Return a valid OAuth access token."""
        await self.session.async_ensure_token_valid()
        return cast("str", self.session.token["access_token"])

    async def _async_get_cloud_devices(
        self, *, cooldown: timedelta | None = None
    ) -> list[GatewayDevice] | None:
        """Get typed device data from the Daikin cloud, respecting cooldown."""
        async with self._cloud_lock:
            if (
                cooldown is not None
                and self._last_patch_call is not None
                and dt_util.utcnow() - self._last_patch_call < cooldown
            ):
                return None
            return await self._client.get_gateway_devices()

    async def async_get_sites(self) -> list[Site]:
        """Return account sites for explicit, non-polling diagnostics."""
        async with self._cloud_lock:
            return await self._client.get_sites()

    async def async_execute_command(
        self, command: Callable[[OnectaClient], Awaitable[None]]
    ) -> bool:
        """Run a cloud command and retain failure context in debug logging."""
        async with self._cloud_lock:
            try:
                await command(self._client)
            except OAuth2TokenRequestReauthError:
                self.config_entry.async_start_reauth(self.hass)
                return False
            except OAuth2TokenRequestError:
                return False
            except OnectaAuthenticationError:
                self.config_entry.async_start_reauth(self.hass)
                return False
            except OnectaRateLimitError as err:
                _LOGGER.debug(
                    "Daikin request %s %s was rate limited; retry after %s seconds",
                    err.method,
                    err.path,
                    err.retry_after,
                )
                return False
            except OnectaConnectionError as err:
                _LOGGER.debug(
                    "Daikin request %s %s failed to connect: %s",
                    err.method,
                    err.path,
                    err,
                )
                return False
            except OnectaApiError as err:
                _LOGGER.debug(
                    "Daikin request %s %s failed with HTTP %s",
                    err.method,
                    err.path,
                    err.status,
                )
                return False
            except TimeoutError:
                _LOGGER.debug("Daikin request timed out")
                return False
            self._last_patch_call = dt_util.utcnow()
            return True

    def async_register_devices(self) -> None:
        """Register all gateways before forwarding platform setup."""
        for device in (self.data or {}).values():
            self._async_register_device(device)

    def _async_register_device(self, device: DaikinOnectaDevice) -> None:
        """Refresh gateway metadata in the Home Assistant device registry."""
        gateway = device.device
        connections = (
            {(CONNECTION_NETWORK_MAC, gateway.mac_address)}
            if gateway.mac_address
            else set()
        )
        model, serial_number, sw_version = (
            (point.model, point.serial, point.version)
            if (point := gateway.gateway_management_point) is not None
            else (None, None, None)
        )
        registry = dr.async_get(self.hass)
        if (
            existing_entry := registry.async_get_device_by_identifier(
                (DOMAIN, device.id), self.config_entry.entry_id
            )
        ) is not None and existing_entry.connections != connections:
            registry.async_update_device(existing_entry.id, new_connections=connections)
        gateway_entry = registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, device.id)},
            connections=connections,
            manufacturer="Daikin",
            model=model,
            model_id=gateway.device_model,
            name=device.name,
            serial_number=serial_number,
            sw_version=sw_version,
        )
        for point in getattr(gateway, "management_points", []):
            if point.management_point_type not in MANAGEMENT_POINT_DEVICE_NAMES:
                continue
            registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                identifiers={(DOMAIN, f"{device.id}_{point.embedded_id}")},
                manufacturer="Daikin",
                model=point.model,
                name=(
                    f"{device.name} "
                    f"{MANAGEMENT_POINT_DEVICE_NAMES[point.management_point_type]}"
                ),
                serial_number=point.serial,
                sw_version=point.version,
                via_device_id=gateway_entry.id,
            )

    @property
    def cloud_update_sequence(self) -> int:
        """Identify fresh cloud responses separately from local write notifications."""
        return self._cloud_update_sequence

    async def _async_update_data_from_cloud(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch the latest device state from Daikin."""
        previous_devices = self.data
        devices = previous_devices or {}
        if (
            self.last_patch_call is not None
            and (dt_util.utcnow() - self.last_patch_call).total_seconds()
            < _POST_WRITE_COOLDOWN.total_seconds()
        ):
            self.update_interval = _POST_WRITE_COOLDOWN
        else:
            # Restore the normal polling interval before fetching. If the
            # request fails, retries must not remain at the cooldown cadence.
            self.update_interval = self._determine_update_interval()
            try:
                cloud_devices = await self._async_get_cloud_devices(
                    cooldown=_POST_WRITE_COOLDOWN
                )
            except OAuth2TokenRequestError:
                # Preserve refresh-token failures so Home Assistant can handle
                # authentication failures rather than retrying the coordinator.
                raise
            except OnectaRateLimitError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="rate_limit_exceeded",
                    retry_after=err.retry_after,
                ) from err
            except OnectaConnectionError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="connection_failed",
                ) from err
            except OnectaAuthenticationError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                ) from err
            except OnectaApiError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={"status": str(err.status)},
                ) from err

            if cloud_devices is None:
                self.update_interval = _POST_WRITE_COOLDOWN
            else:
                self._cloud_update_sequence += 1
                has_new_topology = previous_devices is not None and bool(
                    self._topology(cloud_devices)
                    - self._topology(
                        device.device for device in previous_devices.values()
                    )
                )
                cloud_device_ids = {device.id for device in cloud_devices}
                for device_id, device in devices.items():
                    if device_id not in cloud_device_ids:
                        device.mark_unavailable()

                for dev_data in cloud_devices:
                    if dev_data.id in devices:
                        device = devices[dev_data.id]
                        registry_metadata_changed = device.set_device_data(dev_data)
                    else:
                        device = DaikinOnectaDevice(dev_data)
                        devices[dev_data.id] = device
                        registry_metadata_changed = True
                    if registry_metadata_changed:
                        self._async_register_device(device)

                if has_new_topology and not self._reload_pending:
                    # Platform setup is capability-driven. Reload only when the
                    # cloud reports newly supported entities, including new
                    # capabilities of existing management points.
                    # Missing controls remain registered but unavailable.
                    self._reload_pending = True
                    self.hass.config_entries.async_schedule_reload(
                        self.config_entry.entry_id
                    )

                self.update_interval = self._determine_update_interval()

        return devices

    @override
    async def _async_update_data(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch data for the Home Assistant coordinator interface."""
        return await self._async_update_data_from_cloud()

    @staticmethod
    def _topology(
        devices: Iterable[GatewayDevice],
    ) -> set[tuple[str, str | None, str]]:
        """Return supported entity identities, independent of their current values."""
        return {
            entity_key
            for device in devices
            for entity_key in gateway_entity_keys(device)
        }

    def _determine_update_interval(self) -> timedelta:
        """Determine the next polling interval."""
        now = dt_util.now()
        high_interval, low_interval = self._polling_intervals()
        scan_interval = int(low_interval.total_seconds())
        high_scan_interval = int(high_interval.total_seconds())
        hs = _HIGH_SCAN_START
        ls = _LOW_SCAN_START
        in_high_frequency_window = self._in_between(now.time(), hs, ls)
        if in_high_frequency_window:
            scan_interval = high_scan_interval
        else:
            # When switching from high to low frequency polling we need to randomize the first
            # poll so that we spread the load to daikin, so for example when we have a low start at
            # 22:00 and a high scan interval of 9 minutes we randomize the next poll when it is
            # between 22:00 and 22:09
            end_time = (
                dt_util.start_of_local_day()
                + timedelta(
                    hours=ls.hour,
                    minutes=ls.minute,
                    seconds=ls.second + high_scan_interval,
                )
            ).time()
            if self._in_between(now.time(), ls, end_time):
                scan_interval = random.randint(high_scan_interval, scan_interval)

        if hs != ls:
            boundary = ls if in_high_frequency_window else hs
            now_utc = dt_util.as_utc(now)
            next_boundary = datetime.combine(
                now.date(), boundary, dt_util.DEFAULT_TIME_ZONE
            ).replace(fold=now.fold)
            if dt_util.as_utc(next_boundary) <= now_utc:
                # During the first occurrence of the daylight-saving rollback
                # hour, the same local boundary can occur once more today.
                repeated_boundary = next_boundary.replace(fold=1)
                if dt_util.as_utc(repeated_boundary) > now_utc:
                    next_boundary = repeated_boundary
                else:
                    next_boundary = datetime.combine(
                        now.date() + timedelta(days=1),
                        boundary,
                        dt_util.DEFAULT_TIME_ZONE,
                    )
            next_boundary_utc = dt_util.as_utc(next_boundary)
            boundary_delay = int((next_boundary_utc - now_utc).total_seconds())
            if self._is_nonexistent_local_time(next_boundary):
                # A local boundary in the spring-forward gap resolves later
                # than the clock transition. Poll at the transition so the
                # next calculation can apply the active window's interval.
                boundary_delay = int(
                    (
                        self._next_clock_transition(
                            now_utc, next_boundary_utc, next_boundary.tzinfo
                        )
                        - now_utc
                    ).total_seconds()
                )
                scan_interval = min(
                    scan_interval, max(high_scan_interval, boundary_delay)
                )
            else:
                # Keep a valid polling interval when the next boundary is less
                # than one high-frequency interval away. In particular, converting
                # a fractional-second delay to an integer must not result in zero.
                scan_interval = max(
                    high_scan_interval, min(scan_interval, boundary_delay)
                )

        return timedelta(seconds=scan_interval)

    def _polling_intervals(self) -> tuple[timedelta, timedelta]:
        """Return polling intervals within the available daily API-call budget."""
        rate_limit = self.client.rate_limit.day_limit
        daily_limit = (
            rate_limit
            if isinstance(rate_limit, int) and rate_limit > 0
            else _DEFAULT_DAILY_CALL_LIMIT
        )
        daily_budget = max(2, int(daily_limit * _POLLING_BUDGET_FRACTION))

        high_window_seconds = (
            datetime.combine(datetime.min, _LOW_SCAN_START)
            - datetime.combine(datetime.min, _HIGH_SCAN_START)
        ).total_seconds() % timedelta(days=1).total_seconds()
        low_window_seconds = timedelta(days=1).total_seconds() - high_window_seconds
        interval_ratio = _LOW_SCAN_INTERVAL / _HIGH_SCAN_INTERVAL
        minimum_interval = int(_MINIMUM_POLL_INTERVAL.total_seconds())
        high_interval = max(
            minimum_interval,
            ceil(
                (high_window_seconds + low_window_seconds / interval_ratio)
                / daily_budget
            ),
        )
        low_interval = max(minimum_interval, ceil(high_interval * interval_ratio))

        while (
            ceil(high_window_seconds / high_interval)
            + ceil(low_window_seconds / low_interval)
            > daily_budget
        ):
            high_interval += 1
            low_interval = max(minimum_interval, ceil(high_interval * interval_ratio))

        return timedelta(seconds=high_interval), timedelta(seconds=low_interval)

    @staticmethod
    def _in_between(now: time, start: time, end: time) -> bool:
        """Return whether now is between start and end, including overnight ranges."""
        if start <= end:
            return start <= now < end
        return start <= now or now < end

    @staticmethod
    def _is_nonexistent_local_time(value: datetime) -> bool:
        """Return whether an aware datetime falls within a clock-forward gap."""
        assert value.tzinfo is not None
        return dt_util.as_utc(value).astimezone(value.tzinfo).replace(
            tzinfo=None
        ) != value.replace(tzinfo=None)

    @staticmethod
    def _next_clock_transition(
        start: datetime, end: datetime, timezone: tzinfo | None
    ) -> datetime:
        """Return the first UTC offset transition between two UTC datetimes."""
        assert timezone is not None
        offset = start.astimezone(timezone).utcoffset()
        assert end.astimezone(timezone).utcoffset() != offset

        while end - start > timedelta(seconds=1):
            midpoint = start + (end - start) / 2
            if midpoint.astimezone(timezone).utcoffset() == offset:
                start = midpoint
            else:
                end = midpoint
        return end
