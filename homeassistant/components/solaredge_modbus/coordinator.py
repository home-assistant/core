"""DataUpdateCoordinators for the SolarEdge Modbus integration."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final, override

from solaredged import SolarEdge, SolarEdgeConnectionError, UpdateReport

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LOGGER,
    SUBSYSTEM_ADVANCED_POWER_CONTROL,
    SUBSYSTEM_COMMON,
    SUBSYSTEM_POWER_CONTROL,
    SUBSYSTEM_SITE_CONTROL,
)

type SolarEdgeModbusConfigEntry = ConfigEntry[SolarEdgeModbusRuntimeData]

SETTINGS_SUBSYSTEMS: Final = frozenset(
    {
        SUBSYSTEM_ADVANCED_POWER_CONTROL,
        SUBSYSTEM_POWER_CONTROL,
        SUBSYSTEM_SITE_CONTROL,
    }
)


def _merge(first: UpdateReport, second: UpdateReport) -> UpdateReport:
    """Fold a retried poll into the one it followed.

    A sub-system that answered either attempt holds fresh values, so only the
    ones that stayed silent throughout count as failed.
    """
    return UpdateReport(
        updated=first.updated | second.updated,
        failed={
            subsystem: error
            for subsystem, error in second.failed.items()
            if subsystem not in first.updated
        },
    )


class SolarEdgeModbusDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Polls one set of the inverter's sub-systems over Modbus.

    A poll can come back partial: the library reads every sub-system on its
    own, so one that falls silent no longer takes the others down with it. The
    report names what refreshed, which is what entities read their availability
    from.
    """

    config_entry: SolarEdgeModbusConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SolarEdgeModbusConfigEntry,
        solaredge: SolarEdge,
        *,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
        label: str,
    ) -> None:
        """Initialize the coordinator."""
        self.solaredge = solaredge
        self._poll = poll
        self._silent: set[str] = set()
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            # The serial number identifies this inverter, but it would also end
            # up in every log line a name is written to, so the title stands in.
            name=f"{entry.title} {label}",
            update_interval=interval,
        )

    @override
    async def _async_update_data(self) -> UpdateReport:
        """Poll the inverter, reporting what answered."""
        report = await self._async_poll()

        # A sub-system that just fell silent gets a second chance: SolarEdge
        # answers a single request late often enough that one blip should not
        # blank its entities. One that has been silent a while does not, so a
        # sub-system that is really gone cannot double every poll from here on.
        if report.failed.keys() - self._silent:
            report = await self._async_retry(report)

        # An address can move to another inverter, and its measurements are not
        # this one's however the entities reading them are named. Checked on
        # every poll that brought the identity along, not only at setup.
        if (
            SUBSYSTEM_COMMON in report.updated
            and self.solaredge.common.serial_number != self.config_entry.unique_id
        ):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="wrong_inverter",
            )

        self._log_silence(report)

        return report

    async def _async_retry(self, report: UpdateReport) -> UpdateReport:
        """Poll again, keeping the first attempt's report if the retry dies.

        A link that drops between the two attempts does not make values from a
        second ago stale, and failing the whole refresh would blank every
        sub-system that did answer. The next poll reports the dead link soon
        enough.
        """
        try:
            retried = await self._poll()
        except SolarEdgeConnectionError as err:
            LOGGER.debug(
                "%s: nothing answered the retry (%s); keeping the first poll",
                self.name,
                err,
            )
            return report

        return _merge(report, retried)

    async def _async_poll(self) -> UpdateReport:
        """Poll the inverter's sub-systems, translating a dead link."""
        try:
            return await self._poll()
        except SolarEdgeConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

    def _log_silence(self, report: UpdateReport) -> None:
        """Log a sub-system falling silent once, and log its return."""
        for subsystem, error in report.failed.items():
            if subsystem not in self._silent:
                self._silent.add(subsystem)
                LOGGER.warning(
                    "%s: %s did not answer this poll and kept its previous values: %s",
                    self.name,
                    subsystem,
                    error,
                )

        for subsystem in report.updated & self._silent:
            self._silent.discard(subsystem)
            LOGGER.info("%s: %s is answering again", self.name, subsystem)


@dataclass(kw_only=True)
class SolarEdgeModbusRuntimeData:
    """Runtime data for a SolarEdge Modbus config entry."""

    readings: SolarEdgeModbusDataUpdateCoordinator
    settings: SolarEdgeModbusDataUpdateCoordinator
    device_info: DeviceInfo
    inverter_device_id: str
    # What was attached when this entry was built, to notice a swap: a meter
    # replaced by another one leaves the count alone.
    attachments: frozenset[str]

    # The export mode and its flags share one register, which the library
    # changes by taking its cached value, flipping bits and writing it back.
    # Every platform has its own parallel-update semaphore, so a select and a
    # switch can reach that read-modify-write at once and one loses the other's
    # change; every write goes through this lock instead.
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def solaredge(self) -> SolarEdge:
        """Return the polled device, which both coordinators share."""
        return self.readings.solaredge

    def coordinator_for(self, subsystem: str) -> SolarEdgeModbusDataUpdateCoordinator:
        """Return the coordinator that refreshes a given sub-system."""
        if subsystem in SETTINGS_SUBSYSTEMS:
            return self.settings
        return self.readings
