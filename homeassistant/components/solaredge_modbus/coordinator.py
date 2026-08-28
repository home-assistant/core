"""DataUpdateCoordinator for the SolarEdge Modbus integration."""

from dataclasses import dataclass
from typing import override

from solaredged import SolarEdge, SolarEdgeConnectionError, UpdateReport

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type SolarEdgeModbusConfigEntry = ConfigEntry[SolarEdgeModbusRuntimeData]


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
    """Polls the inverter's sub-systems over Modbus.

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
    ) -> None:
        """Initialize the coordinator."""
        self.solaredge = solaredge
        self._silent: set[str] = set()
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            # The serial number identifies this inverter, but it would also end
            # up in every log line a name is written to, so the title stands in.
            name=f"{entry.title} readings",
            update_interval=SCAN_INTERVAL,
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
            retried = await self.solaredge.async_update_readings()
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
            return await self.solaredge.async_update_readings()
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
    device_info: DeviceInfo

    @property
    def solaredge(self) -> SolarEdge:
        """Return the polled device."""
        return self.readings.solaredge
