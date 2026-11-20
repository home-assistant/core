"""Coordinator for Daikin Onecta integration."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo
import logging
from math import ceil
import random
from typing import Never, cast, override

from aiohttp import ClientError
from daikin_onecta import Site
from daikin_onecta.client import OnectaClient
from daikin_onecta.exceptions import (
    OnectaApiError,
    OnectaAuthenticationError,
    OnectaConnectionError,
    OnectaError,
    OnectaRateLimitError,
    OnectaResponseError,
)
from daikin_onecta.models import GatewayDevice
from daikin_onecta.rate_limit import RateLimit

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    OAuth2TokenRequestBaseError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .device import DaikinOnectaDevice

_LOGGER = logging.getLogger(__name__)

_HIGH_SCAN_INTERVAL = timedelta(minutes=10)
_LOW_SCAN_INTERVAL = timedelta(minutes=30)
_HIGH_SCAN_START = time(7)
_LOW_SCAN_START = time(22)
_POST_WRITE_COOLDOWN = timedelta(seconds=30)
_SITES_DIAGNOSTICS_CACHE_DURATION = timedelta(hours=6)
_DEFAULT_DAILY_CALL_LIMIT = 200
_POLLING_BUDGET_FRACTION = 0.55
_MINIMUM_POLL_INTERVAL = timedelta(minutes=3)

type DaikinOnectaConfigEntry = ConfigEntry[OnectaDataUpdateCoordinator]


def gateway_site_membership(sites: list[Site], gateway_device_id: str) -> bool | None:
    """Return membership without assuming an incomplete site response is empty."""
    # An empty response cannot confirm absence; users can remove the config entry.
    if not sites:
        return None
    membership = [site.has_gateway_device(gateway_device_id) for site in sites]
    if True in membership:
        return True
    return None if None in membership else False


@dataclass(frozen=True)
class SiteLookupResult:
    """Contain an account Sites response and its gateway membership lookup."""

    sites: list[Site]
    error: Exception | None = None

    def gateway_membership(self, gateway_device_id: str) -> bool | None:
        """Return unknown when the Sites request failed."""
        if self.error is not None:
            return None
        return gateway_site_membership(self.sites, gateway_device_id)


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
        self._polling_backoff_until: datetime | None = None
        self._cloud_lock = asyncio.Lock()
        self._cloud_update_sequence = 0
        self._unsub_post_write_refresh: CALLBACK_TYPE | None = None
        self._sites_cache: tuple[datetime, list[Site]] | None = None

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

    async def async_manual_refresh(self) -> bool:
        """Refresh immediately unless Daikin has asked us to wait.

        Return whether a fresh cloud response was received.
        """
        if remaining := (
            self._polling_backoff_remaining() or self._post_write_cooldown_remaining()
        ):
            self._raise_manual_refresh_deferred(remaining)
        # The same backoff check used by scheduled and entity refreshes runs
        # again after acquiring the cloud lock.
        previous_sequence = self._cloud_update_sequence
        await self.async_refresh()
        if remaining := (
            self._polling_backoff_remaining() or self._post_write_cooldown_remaining()
        ):
            self._raise_manual_refresh_deferred(remaining)
        return self._cloud_update_sequence > previous_sequence

    @staticmethod
    def _raise_manual_refresh_deferred(remaining: timedelta) -> Never:
        """Raise the translated error when a manual refresh is deferred."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="manual_refresh_deferred",
            translation_placeholders={"seconds": str(ceil(remaining.total_seconds()))},
        )

    def _post_write_cooldown_remaining(self) -> timedelta | None:
        """Return the remaining post-write cooldown, if any."""
        if self._last_patch_call is None:
            return None
        remaining = _POST_WRITE_COOLDOWN - (dt_util.utcnow() - self._last_patch_call)
        return remaining if remaining > timedelta(0) else None

    async def _async_get_cloud_devices(self) -> list[GatewayDevice] | None:
        """Get typed device data from the Daikin cloud, respecting cooldown."""
        async with self._cloud_lock:
            if self._polling_backoff_remaining() is not None:
                return None
            if self._post_write_cooldown_remaining() is not None:
                return None
            try:
                return await self._client.get_gateway_devices()
            except OnectaRateLimitError as err:
                self._set_polling_backoff(err.retry_after)
                raise

    async def async_get_sites(self, *, use_cache: bool = False) -> list[Site]:
        """Return account sites unless Daikin's rate-limit backoff is active.

        Diagnostics may reuse a recent result because the Sites request also
        consumes the account's cloud quota. Device-removal checks stay fresh.
        """
        async with self._cloud_lock:
            if use_cache and self._sites_cache is not None:
                cached_at, sites = self._sites_cache
                if dt_util.utcnow() - cached_at < _SITES_DIAGNOSTICS_CACHE_DURATION:
                    return sites
            if remaining := self._polling_backoff_remaining():
                # Keep the shared polling backoff in force for explicit Sites
                # lookups too; manual device refresh remains a separate path.
                raise OnectaRateLimitError(
                    RateLimit(retry_after=ceil(remaining.total_seconds())),
                    method="GET",
                    path="/v1/sites",
                )
            try:
                sites = await self._client.get_sites()
                self._sites_cache = (dt_util.utcnow(), sites)
            except OnectaRateLimitError as err:
                self._set_polling_backoff(err.retry_after)
                raise
            else:
                return sites

    async def async_get_site_lookup(
        self, *, use_cache: bool = False, start_reauth: bool = False
    ) -> SiteLookupResult:
        """Get Sites and normalize expected lookup failures for callers."""
        try:
            sites = await self.async_get_sites(use_cache=use_cache)
        except OAuth2TokenRequestReauthError as err:
            if start_reauth:
                self.config_entry.async_start_reauth(self.hass)
            return SiteLookupResult([], err)
        except OnectaAuthenticationError as err:
            if start_reauth and err.status == 401:
                self.config_entry.async_start_reauth(self.hass)
            return SiteLookupResult([], err)
        except (
            OAuth2TokenRequestError,
            OnectaError,
            ClientError,
            TimeoutError,
        ) as err:
            return SiteLookupResult([], err)
        return SiteLookupResult(sites)

    def _polling_backoff_remaining(self) -> timedelta | None:
        """Return the remaining polling backoff, if any."""
        if self._polling_backoff_until is None:
            return None
        remaining = self._polling_backoff_until - dt_util.utcnow()
        if remaining <= timedelta(0):
            self._polling_backoff_until = None
            _LOGGER.info("Daikin polling rate-limit backoff ended")
            return None
        return timedelta(seconds=ceil(remaining.total_seconds()))

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
            except OAuth2TokenRequestBaseError as err:
                _LOGGER.debug(
                    "Daikin OAuth token request failed with %s",
                    type(err).__name__,
                )
                return False
            except OnectaAuthenticationError as err:
                if err.status == 401:
                    _LOGGER.debug(
                        "Daikin request %s %s failed authentication with HTTP %s",
                        err.method,
                        err.path,
                        err.status,
                    )
                    self.config_entry.async_start_reauth(self.hass)
                else:
                    _LOGGER.debug(
                        "Daikin request %s %s was not authorized with HTTP %s",
                        err.method,
                        err.path,
                        err.status,
                    )
                return False
            except OnectaRateLimitError as err:
                self._set_polling_backoff(err.retry_after)
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
            had_polling_backoff = self._polling_backoff_remaining() is not None
            self._polling_backoff_until = None
            self._last_patch_call = dt_util.utcnow()
            if had_polling_backoff or self._unsub_post_write_refresh is not None:
                self.schedule_post_write_refresh()
            return True

    def schedule_post_write_refresh(self) -> None:
        """Request cloud state after a successful write's cooldown."""
        self._cancel_post_write_refresh()
        self._unsub_post_write_refresh = async_track_point_in_utc_time(
            self.hass,
            self._async_post_write_refresh,
            dt_util.utcnow() + _POST_WRITE_COOLDOWN,
        )

    def _set_polling_backoff(self, retry_after: float | None) -> None:
        """Retain Daikin's Retry-After deadline for every later refresh."""
        if retry_after is None or retry_after <= 0:
            return
        was_active = self._polling_backoff_remaining() is not None
        retry_at = dt_util.utcnow() + timedelta(seconds=retry_after)
        if (
            self._polling_backoff_until is None
            or retry_at > self._polling_backoff_until
        ):
            self._polling_backoff_until = retry_at
            if not was_active:
                _LOGGER.info(
                    "Daikin rate-limited cloud requests; polling paused for %s seconds",
                    ceil(retry_after),
                )

    async def _async_post_write_refresh(self, _now: datetime) -> None:
        """Refresh after the successful write cooldown expires."""
        self._unsub_post_write_refresh = None
        await self.async_refresh()

    @callback
    def _cancel_post_write_refresh(self) -> None:
        """Cancel a pending post-write refresh."""
        if self._unsub_post_write_refresh is not None:
            self._unsub_post_write_refresh()
            self._unsub_post_write_refresh = None

    @override
    async def async_shutdown(self) -> None:
        """Cancel the post-write refresh timer when shutting down."""
        self._cancel_post_write_refresh()
        await super().async_shutdown()

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
        model, serial_number, sw_version = device.gateway_metadata
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
        device.ha_device_id = gateway_entry.id

    @property
    def cloud_update_sequence(self) -> int:
        """Identify fresh cloud responses separately from local write notifications."""
        return self._cloud_update_sequence

    async def _async_update_data_from_cloud(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch the latest device state from Daikin."""
        previous_devices = self.data_or_none
        devices = previous_devices or {}
        if (remaining := self._polling_backoff_remaining()) is not None:
            self.update_interval = remaining
            if not self.last_update_success or previous_devices is None:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="rate_limit_exceeded",
                    retry_after=remaining.total_seconds(),
                )
            return devices

        if self._post_write_cooldown_remaining() is not None:
            self.update_interval = _POST_WRITE_COOLDOWN
            if not self.last_update_success:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="refresh_deferred",
                    retry_after=_POST_WRITE_COOLDOWN.total_seconds(),
                )
        else:
            # Restore the normal polling interval before fetching. If the
            # request fails, retries must not remain at the cooldown cadence.
            self.update_interval = self._determine_update_interval()
            try:
                cloud_devices = await self._async_get_cloud_devices()
            except OAuth2TokenRequestReauthError as err:
                # Convert reauth failures so the coordinator notifies entities
                # that their state is no longer current.
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                ) from err
            except OAuth2TokenRequestError:
                # Preserve transient token errors so the coordinator retries.
                raise
            except OnectaRateLimitError as err:
                if self.last_update_success and previous_devices is not None:
                    # Preserve known-good entities while every refresh waits
                    # for Daikin's Retry-After deadline.
                    if remaining := self._polling_backoff_remaining():
                        self.update_interval = remaining
                    _LOGGER.debug(
                        "Daikin rate-limited a refresh; retaining cached state"
                    )
                    return devices
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="rate_limit_exceeded",
                    retry_after=err.retry_after,
                ) from err
            except OnectaConnectionError as err:
                raise UpdateFailedUnreachable(
                    translation_domain=DOMAIN,
                    translation_key="connection_failed",
                ) from err
            except OnectaAuthenticationError as err:
                # A listing 401 or 403 invalidates account access; a command 403
                # only denies that characteristic and does not justify reauth.
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                ) from err
            except OnectaResponseError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_response",
                ) from err
            except OnectaApiError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={"status": str(err.status)},
                ) from err

            if cloud_devices is None:
                retry_after = self._polling_backoff_remaining() or _POST_WRITE_COOLDOWN
                self.update_interval = retry_after
                if not self.last_update_success:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key=(
                            "rate_limit_exceeded"
                            if self._polling_backoff_until is not None
                            else "refresh_deferred"
                        ),
                        retry_after=retry_after.total_seconds(),
                    )
            else:
                self._cloud_update_sequence += 1
                cloud_device_ids = {device.id for device in cloud_devices}
                for device_id, device in devices.items():
                    if device_id not in cloud_device_ids:
                        device.mark_unavailable()

                for dev_data in cloud_devices:
                    if dev_data.id in devices:
                        device = devices[dev_data.id]
                        was_present = device.present_in_cloud
                        registry_metadata_changed = (
                            device.set_device_data(dev_data) or not was_present
                        )
                    else:
                        device = DaikinOnectaDevice(dev_data)
                        devices[dev_data.id] = device
                        registry_metadata_changed = True
                    if registry_metadata_changed and previous_devices is not None:
                        self._async_register_device(device)

                self.update_interval = self._determine_update_interval()

        return devices

    @override
    async def _async_update_data(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch data for the Home Assistant coordinator interface."""
        return await self._async_update_data_from_cloud()

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
        if value.tzinfo is None:
            raise ValueError("Local time must be timezone-aware")
        return dt_util.as_utc(value).astimezone(value.tzinfo).replace(
            tzinfo=None
        ) != value.replace(tzinfo=None)

    @staticmethod
    def _next_clock_transition(
        start: datetime, end: datetime, timezone: tzinfo | None
    ) -> datetime:
        """Return the first UTC offset transition between two UTC datetimes."""
        if timezone is None:
            raise ValueError("Timezone is required to find a clock transition")
        offset = start.astimezone(timezone).utcoffset()
        if end.astimezone(timezone).utcoffset() == offset:
            raise ValueError("Datetimes do not span a clock transition")

        while end - start > timedelta(seconds=1):
            midpoint = start + (end - start) / 2
            if midpoint.astimezone(timezone).utcoffset() == offset:
                start = midpoint
            else:
                end = midpoint
        return end
