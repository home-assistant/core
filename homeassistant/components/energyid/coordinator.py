"""Coordinator for EnergyID directives."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from aiohttp import ClientError
from energyid_webhooks.client_v2 import WebhookClient
from energyid_webhooks.directives import (
    DirectiveData,
    DirectiveResource,
    DirectiveSignal,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
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


class EnergyIDDirectiveCoordinator(
    DataUpdateCoordinator[dict[str, EnergyIDDirectiveSnapshot]]
):
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
        # None until fetched once; an empty dict means no directives are granted.
        self.available_resources: dict[str, DirectiveResource] | None = None
        self._access_checked_without_token = False

    @override
    async def _async_update_data(
        self,
    ) -> dict[str, EnergyIDDirectiveSnapshot]:
        """Fetch all directives made available to this linked device."""
        if not self.directives_enabled:
            self.available_resources = {}
            return {}

        try:
            if not isinstance(self.client.api_access_token, str):
                if not self._access_checked_without_token:
                    self._access_checked_without_token = True
                    return {}
                await self.client.authenticate()
                if not isinstance(self.client.api_access_token, str):
                    return {}
            resources = await self.client.get_directives()
        except PermissionError:
            return {}
        except (ClientError, OSError, TimeoutError, ValueError) as err:
            if self.available_resources is None:
                _LOGGER.debug("Directives are unavailable during setup: %s", err)
                return {}
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="directives_update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        self.available_resources = {resource.id: resource for resource in resources}

        async def async_get_schedule(
            resource: DirectiveResource,
        ) -> DirectiveData | None:
            try:
                return await self.client.get_directive_data(resource.id)
            except (
                PermissionError,
                ClientError,
                OSError,
                TimeoutError,
                ValueError,
            ) as err:
                _LOGGER.debug(
                    "EnergyID directive %s is unavailable: %s", resource.id, err
                )
                return None

        schedules = await asyncio.gather(
            *(async_get_schedule(resource) for resource in resources)
        )

        now = dt_util.utcnow()
        snapshots: dict[str, EnergyIDDirectiveSnapshot] = {}
        for resource, schedule in zip(resources, schedules, strict=True):
            if schedule is None:
                continue
            current = max(
                (point for point in schedule.data if point.timestamp <= now),
                key=lambda point: point.timestamp,
                default=None,
            )
            next_change = next(
                (
                    point
                    for point in schedule.data
                    if point.timestamp > now
                    and (current is None or point.signal != current.signal)
                ),
                None,
            )
            snapshots[resource.id] = EnergyIDDirectiveSnapshot(
                resource=resource,
                schedule=schedule,
                current=current,
                next_change=next_change,
            )
        return snapshots


@dataclass
class EnergyIDRuntimeData:
    """Runtime data for the EnergyID integration."""

    client: WebhookClient
    directive_coordinator: EnergyIDDirectiveCoordinator
    mappings: dict[str, str]
    state_listener: CALLBACK_TYPE | None = None
    registry_tracking_listener: CALLBACK_TYPE | None = None
    unavailable_logged: bool = False
