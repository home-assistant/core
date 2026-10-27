"""DataUpdateCoordinators for the SolarEdge Modbus integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, override

from solaredged import InverterStatus, SolarEdge, SolarEdgeConnectionError, UpdateReport

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LOGGER,
    SLEEP_OUTAGE_GRACE,
    SLEEP_RESET_MIN_GAP,
    SUBSYSTEM_ADVANCED_POWER_CONTROL,
    SUBSYSTEM_COMMON,
    SUBSYSTEM_INVERTER,
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


@dataclass(kw_only=True)
class SleepState:
    """When the inverter was last read asleep, shared by both coordinators.

    Only the readings poll reads the inverter, but a reset takes the settings
    poll down just the same, so both count from that read.
    """

    # Event loop time, which a clock change does not move. None when the last
    # read that reached the inverter found it awake.
    asleep_at: float | None = None


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
        sleep: SleepState,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
        label: str,
    ) -> None:
        """Initialize the coordinator."""
        self.solaredge = solaredge
        self._sleep = sleep
        self._poll = poll
        self._silent: set[str] = set()
        # When this coordinator's current run of failed polls began, counted
        # from the first one's start, and when that first one failed. The two
        # differ by however long the poll waited, for the link or for the other
        # coordinator's requests.
        self._outage: tuple[float, float] | None = None
        # When the last outage taken for a reset began, as in _outage.
        self._last_reset: float | None = None
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
        # A failed poll counts from its start, so its own connect timeout does
        # not use up the reset window.
        started = self.hass.loop.time()
        try:
            report = await self._poll()
        except SolarEdgeConnectionError as err:
            return self._failed_poll(err, started)
        self._outage = None

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

        self._note_sleep(report)
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

    def _note_sleep(self, report: UpdateReport) -> None:
        """Record whether this poll read the inverter asleep.

        Only a fresh read counts, so a status kept from an earlier poll leaves
        the last one standing, and the window bounds how old that can be. It is
        stamped when the poll is done, so a slow poll and its retry do not use
        up the window either. If the retry died, the link may be gone by then
        already, which moves the window by no more than that retry took.
        """
        if SUBSYSTEM_INVERTER in report.updated:
            asleep = self.solaredge.inverter.status is InverterStatus.SLEEPING
            self._sleep.asleep_at = self.hass.loop.time() if asleep else None

    def _failed_poll(
        self, err: SolarEdgeConnectionError, started: float
    ) -> UpdateReport:
        """Handle a poll that brought nothing back.

        Every value is stale then, so every sub-system counts as failed. If the
        inverter was read asleep shortly before the failures began, and they
        have not gone on for longer than a reset takes, that is all it takes:
        the entities go unavailable without an error. A sleeping read after
        the first failure proves the link worked meanwhile, so it excuses
        nothing, but one between that poll's start and its failure is fine:
        the other coordinator's poll can finish while this one waits. Nor is a
        poll that read the inverter awake before the link died: it never got
        to record that, but the status it read is there. Nor is an outage that
        began soon after the last one taken for a reset: the inverter resets
        a few times a night, hours apart, so a link that keeps dropping in
        between is failing. Anything else is an error as before, and once it
        is, so is every failure until a poll succeeds. The first refresh has
        nothing to mark failed, and setup must see it.
        """
        if self._outage is None:
            self._outage = (started, self.hass.loop.time())
        outage_since, outage_failed_at = self._outage
        asleep_at = self._sleep.asleep_at
        grace = SLEEP_OUTAGE_GRACE.total_seconds()
        last_reset = self._last_reset
        if (
            self.data is not None
            and self.last_update_success
            and asleep_at is not None
            and self.solaredge.inverter.status is InverterStatus.SLEEPING
            and asleep_at <= outage_failed_at
            and outage_since - asleep_at < grace
            and started - outage_since < grace
            and (
                last_reset is None
                or last_reset == outage_since
                or outage_since - last_reset >= SLEEP_RESET_MIN_GAP.total_seconds()
            )
        ):
            self._last_reset = outage_since
            LOGGER.debug(
                "%s: nothing answered the sleeping inverter's poll (%s)",
                self.name,
                err,
            )
            return UpdateReport(
                updated=set(),
                failed=dict.fromkeys(self.data.updated | self.data.failed.keys(), err),
            )

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

    # Blocks that answered nothing while setting up and nothing again on the
    # first check after it. Asking costs a full timeout each, which on a shared
    # link is time every other inverter spends waiting, so they are taken for
    # absent until the entry loads again. Empty until that first check, so a
    # block that was merely busy at setup still gets picked up.
    settled_silent_blocks: frozenset[str] = frozenset()

    @property
    def solaredge(self) -> SolarEdge:
        """Return the polled device, which both coordinators share."""
        return self.readings.solaredge

    def coordinator_for(self, subsystem: str) -> SolarEdgeModbusDataUpdateCoordinator:
        """Return the coordinator that refreshes a given sub-system."""
        if subsystem in SETTINGS_SUBSYSTEMS:
            return self.settings
        return self.readings
