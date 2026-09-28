"""Coordinator for EnergyID directives."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
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
class EnergyIDDirectiveSnapshot:
    """Fetched schedule of one directive with its current and next signal."""

    resource: DirectiveResource
    schedule: DirectiveData
    current: DirectiveSignal | None
    next_change: DirectiveSignal | None


@dataclass(frozen=True)
class EnergyIDDirectivesData:
    """Directives granted to the linked device and their fetched schedules."""

    resources: dict[str, DirectiveResource]
    schedules: dict[str, EnergyIDDirectiveSnapshot]


class EnergyIDDirectiveCoordinator(DataUpdateCoordinator[EnergyIDDirectivesData]):
    """Poll record-scoped directives without affecting outbound uploads."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
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

    @override
    async def _async_update_data(self) -> EnergyIDDirectivesData:
        """Fetch all directives granted to this linked device."""
        if not self.directives_enabled:
            return EnergyIDDirectivesData(resources={}, schedules={})

        try:
            if not isinstance(self.client.api_access_token, str):
                await self.client.authenticate()
            resources = await self.client.get_directives()
        except PermissionError:
            return EnergyIDDirectivesData(resources={}, schedules={})
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_credentials",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="directives_update_failed",
            ) from err
        except (ClientError, OSError, TimeoutError, ValueError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="directives_update_failed",
            ) from err

        schedules = await asyncio.gather(
            *(self._async_get_schedule(resource) for resource in resources)
        )
        now = dt_util.utcnow()
        snapshots = {
            resource.id: _snapshot(resource, schedule, now)
            for resource, schedule in zip(resources, schedules, strict=True)
            if schedule is not None
        }
        return EnergyIDDirectivesData(
            resources={resource.id: resource for resource in resources},
            schedules=snapshots,
        )

    async def _async_get_schedule(
        self, resource: DirectiveResource
    ) -> DirectiveData | None:
        """Return the schedule of one directive, or None when it is unavailable."""
        try:
            return await self.client.get_directive_data(resource.id)
        except (PermissionError, ClientError, OSError, TimeoutError, ValueError) as err:
            _LOGGER.debug("EnergyID directive %s is unavailable: %s", resource.id, err)
            return None


def _snapshot(
    resource: DirectiveResource, schedule: DirectiveData, now: datetime
) -> EnergyIDDirectiveSnapshot:
    """Derive the current and next signal of a directive from its schedule."""
    current = max(
        (point for point in schedule.data if point.timestamp <= now),
        key=lambda point: point.timestamp,
        default=None,
    )
    interval = dt_util.parse_duration(schedule.interval)
    if current and interval and now >= current.timestamp + interval:
        current = None
    next_change = next(
        (
            point
            for point in schedule.data
            if point.timestamp > now
            and (current is None or point.signal != current.signal)
        ),
        None,
    )
    return EnergyIDDirectiveSnapshot(
        resource=resource, schedule=schedule, current=current, next_change=next_change
    )


@dataclass
class EnergyIDRuntimeData:
    """Runtime data for the EnergyID integration."""

    client: WebhookClient
    directive_coordinator: EnergyIDDirectiveCoordinator
    mappings: dict[str, str]
    state_listener: CALLBACK_TYPE | None = None
    registry_tracking_listener: CALLBACK_TYPE | None = None
    unavailable_logged: bool = False
