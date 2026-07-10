"""Habitron integration using DataUpdateCoordinator."""

import asyncio
import logging
from typing import override

from habitron_client import HabitronError, HabitronTimeoutError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .communicate import HbtnComm
from .const import DOMAIN, SCAN_INTERVAL
from .smart_hub import SmartHub

type HabitronConfigEntry = ConfigEntry[HbtnCoordinator]
"""Typed config entry alias. ``entry.runtime_data`` holds the HbtnCoordinator,
which owns both the ``HbtnComm`` transport and the ``SmartHub`` model.
"""

_LOGGER = logging.getLogger(__name__)


class HbtnCoordinator(DataUpdateCoordinator[int]):
    """Habitron data update coordinator.

    ``async_system_update`` writes the bus status directly into the
    module/input/output objects, and the entities read from those object
    attributes via their ``_handle_coordinator_update`` callbacks. The
    coordinator acts as a heartbeat that fans out update events.

    ``async_system_update`` returns the raw compact-status bytes, which serve
    as the change-detection key. With ``always_update=False`` the coordinator
    only fans out to the entities when the bus status actually changed between
    ticks, avoiding a needless write of every entity on every tick.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HabitronConfigEntry,
        hbtn_comm: HbtnComm,
    ) -> None:
        """Initialize Habitron update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Habitron updates",
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )
        self.comm = hbtn_comm
        self.config = entry
        self.smart_hub = SmartHub(hass, entry, hbtn_comm)

    @override
    async def _async_setup(self) -> None:
        """Connect and build the model during ``async_config_entry_first_refresh``.

        Runs once before the first ``_async_update_data``: opens the client,
        builds the bus model and registers the hub/bus devices.
        """
        await self.smart_hub.async_setup()

    @override
    async def _async_update_data(self) -> int:
        """Fetch the current Habitron status.

        Returns the compact-status CRC used for change detection;
        ``async_system_update`` also updates the model in place and fires the
        per-member listeners. Connection-level failures (timeouts, network
        errors, refused connections) are converted to ``UpdateFailed`` so the
        coordinator flips ``last_update_success`` to False and every
        ``CoordinatorEntity`` is automatically marked unavailable.
        """
        try:
            async with asyncio.timeout(20):
                crc = await self.comm.async_system_update()
        except (TimeoutError, HabitronTimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_timeout",
            ) from err
        except (OSError, ConnectionError, HabitronError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_network_error",
                translation_placeholders={"error": str(err)},
            ) from err
        # Refresh the hub host-diagnostics outside the try: it swallows its own
        # errors, so a hub-diag hiccup must not mark every entity unavailable.
        await self.smart_hub.update()
        self._update_router_issue()
        return crc

    def _update_router_issue(self) -> None:
        """Mirror the router's system-error flag into the issue registry.

        A router system error is surfaced as a non-fixable (informational)
        repair issue and cleared again once the router recovers.
        """
        router = self.comm.router
        issue_id = f"router_system_error_{router.uid}"
        if router.sys_ok:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        else:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="router_system_error",
            )
