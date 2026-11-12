"""Coordinator for EnergyID directives."""

import asyncio
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import override

from aiohttp import ClientError, ClientResponseError
from energyid_webhooks.client_v2 import WebhookClient
from energyid_webhooks.directives import (
    DirectiveData,
    DirectiveResource,
    DirectiveSignal,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_ENABLE_DIRECTIVES, DOMAIN

_LOGGER = logging.getLogger(__name__)

DIRECTIVE_UPDATE_INTERVAL = timedelta(minutes=5)

type EnergyIDConfigEntry = ConfigEntry[EnergyIDRuntimeData]


@callback
def async_directives_enabled(entry: ConfigEntry) -> bool:
    """Return whether the user opted in to directives; an absent option means no."""
    return bool(entry.options.get(CONF_ENABLE_DIRECTIVES, False))


@dataclass(frozen=True)
class EnergyIDDirectiveState:
    """Signal of a directive at one moment and when it changes next."""

    current: DirectiveSignal | None
    next_change: datetime | None
    next_signal: DirectiveSignal | None


@dataclass(frozen=True)
class EnergyIDDirectiveSnapshot:
    """Fetched schedule of one directive."""

    resource: DirectiveResource
    schedule: DirectiveData

    def state_at(self, moment: datetime) -> EnergyIDDirectiveState:
        """Return the signal at a moment and the first change after it."""
        points = sorted(self.schedule.data, key=lambda point: point.timestamp)
        timestamps = [point.timestamp for point in points]
        interval = dt_util.parse_duration(self.schedule.interval)

        def signal_at(when: datetime) -> DirectiveSignal | None:
            index = bisect_right(timestamps, when)
            if not index:
                return None
            point = points[index - 1]
            if interval and when >= point.timestamp + interval:
                return None
            return point

        current = signal_at(moment)
        boundaries = set(timestamps)
        if interval:
            boundaries.update(timestamp + interval for timestamp in timestamps)
        for boundary in sorted(boundaries):
            if boundary <= moment:
                continue
            signal = signal_at(boundary)
            if _signal_value(signal) != _signal_value(current):
                return EnergyIDDirectiveState(current, boundary, signal)
        return EnergyIDDirectiveState(current, None, None)


@dataclass(frozen=True)
class EnergyIDDirectivesData:
    """Directives granted to the linked device and their fetched schedules."""

    resources: dict[str, DirectiveResource]
    schedules: dict[str, EnergyIDDirectiveSnapshot]


class EnergyIDDirectiveCoordinator(DataUpdateCoordinator[EnergyIDDirectivesData]):
    """Poll record-scoped directives without affecting outbound uploads."""

    config_entry: EnergyIDConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EnergyIDConfigEntry,
        client: WebhookClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN} directives",
            update_interval=DIRECTIVE_UPDATE_INTERVAL,
            config_entry=config_entry,
            always_update=False,
        )
        self.client = client
        self.directives_enabled = async_directives_enabled(config_entry)
        self._unavailable_directives: set[str] = set()
        self._unsub_signal_change: CALLBACK_TYPE | None = None

    @override
    async def _async_update_data(self) -> EnergyIDDirectivesData:
        """Fetch all directives granted to this linked device."""
        if not self.directives_enabled:
            return EnergyIDDirectivesData(resources={}, schedules={})

        try:
            resources = await self.client.get_directives()
        except PermissionError:
            # A denied list can also come from a re-authentication that lost the claim.
            self._raise_if_unclaimed()
            return EnergyIDDirectivesData(resources={}, schedules={})
        except ClientResponseError as err:
            self._raise_if_unclaimed()
            # A 403 means directive access is not granted to this record.
            if err.status == HTTPStatus.FORBIDDEN:
                return EnergyIDDirectivesData(resources={}, schedules={})
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="directives_update_failed",
            ) from err
        except (ClientError, OSError, TimeoutError, ValueError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="directives_update_failed",
            ) from err

        # The client re-authenticates on its own, which can reveal a lost claim.
        self._raise_if_unclaimed()
        schedules = await asyncio.gather(
            *(self._async_get_schedule(resource) for resource in resources)
        )
        self._raise_if_unclaimed()
        return EnergyIDDirectivesData(
            resources={resource.id: resource for resource in resources},
            schedules={
                resource.id: EnergyIDDirectiveSnapshot(resource, schedule)
                for resource, schedule in zip(resources, schedules, strict=True)
                if schedule is not None
            },
        )

    @callback
    @override
    def _async_refresh_finished(self) -> None:
        """Rearm the signal change timer for the fetched schedules."""
        self._schedule_signal_change()

    @callback
    def _schedule_signal_change(self) -> None:
        """Notify entities at the next signal change without an API request."""
        self._cancel_signal_change()
        if self._shutdown_requested or not self.last_update_success or not self.data:
            return
        now = dt_util.utcnow()
        changes = [
            change
            for snapshot in self.data.schedules.values()
            if (change := snapshot.state_at(now).next_change) is not None
        ]
        if changes:
            self._unsub_signal_change = async_track_point_in_utc_time(
                self.hass, self._handle_signal_change, min(changes)
            )

    @callback
    def _handle_signal_change(self, _now: datetime) -> None:
        """Update entities when a signal changes and rearm for the next one."""
        self._unsub_signal_change = None
        self._schedule_signal_change()
        self.async_update_listeners()

    @callback
    def _cancel_signal_change(self) -> None:
        """Cancel the scheduled signal change."""
        if self._unsub_signal_change is not None:
            self._unsub_signal_change()
            self._unsub_signal_change = None

    @override
    async def async_shutdown(self) -> None:
        """Cancel the signal change timer when the coordinator shuts down."""
        await super().async_shutdown()
        self._cancel_signal_change()

    async def _async_get_schedule(
        self, resource: DirectiveResource
    ) -> DirectiveData | None:
        """Return the schedule of one directive, or None when it is unavailable."""
        try:
            schedule = await self.client.get_directive_data(resource.id)
        except ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                self._raise_if_unclaimed()
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="directives_update_failed",
                ) from err
            self._log_unavailable(resource, err)
            return None
        except (PermissionError, ClientError, OSError, TimeoutError, ValueError) as err:
            self._log_unavailable(resource, err)
            return None
        if resource.id in self._unavailable_directives:
            self._unavailable_directives.discard(resource.id)
            _LOGGER.info("EnergyID directive %s is available again", resource.id)
        return schedule

    def _log_unavailable(self, resource: DirectiveResource, err: Exception) -> None:
        """Log once that a directive's schedule became unavailable."""
        if resource.id not in self._unavailable_directives:
            self._unavailable_directives.add(resource.id)
            _LOGGER.info("EnergyID directive %s is unavailable: %s", resource.id, err)

    def _raise_if_unclaimed(self) -> None:
        """Start reauthentication when EnergyID no longer knows the device as claimed."""
        if self.client.is_claimed is False:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="device_not_claimed",
            )


def _signal_value(point: DirectiveSignal | None) -> str | None:
    """Return the signal of a point, or None when no slot is active."""
    return point.signal if point else None


@dataclass
class EnergyIDRuntimeData:
    """Runtime data for the EnergyID integration."""

    client: WebhookClient
    directive_coordinator: EnergyIDDirectiveCoordinator
    mappings: dict[str, str]
    state_listener: CALLBACK_TYPE | None = None
    registry_tracking_listener: CALLBACK_TYPE | None = None
    unavailable_logged: bool = False
