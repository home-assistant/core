"""The coordinator for APsystems local API integration."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any, override

from APsystemsEZ1 import (
    APsystemsEZ1M,
    InverterReturnedError,
    ReturnAlarmInfo,
    ReturnOutputData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER
from .lake6.client import (
    Lake6Alarms,
    Lake6ApiClient,
    Lake6ApiError,
    Lake6ControlPanel,
    Lake6Device,
    Lake6Energies,
    Lake6Modes,
)
from .lake6.const import (
    LAKE6_CONTROL_PANEL_MODE_ACTIVE,
    LAKE6_CONTROL_PANEL_MODE_IDLE,
    LAKE6_CONTROL_PANEL_SETTLE,
    LAKE6_CONTROL_PANEL_START_BACKDATES,
    LAKE6_CONTROL_PANEL_TIME_FORMATS,
    LAKE6_CONTROL_PANEL_UPDATE_INTERVAL,
    LAKE6_MANUAL_MODE_STANDBY,
    LAKE6_MANUAL_MODE_TO_POWER_SIGN,
    LAKE6_MANUAL_POWER_STANDBY,
    LAKE6_MODES_UPDATE_INTERVAL,
    LAKE6_UPDATE_INTERVAL,
)


@dataclass
class ApSystemsSensorData:
    """Representing different Apsystems sensor data."""

    output_data: ReturnOutputData
    alarm_info: ReturnAlarmInfo


@dataclass
class ApSystemsData:
    """Store runtime data."""

    coordinator: ApSystemsDataCoordinator
    device_id: str


@dataclass
class Lake6ManualControl:
    """Pending manual control request, one field per config entity.

    The device clears `MI1` as soon as the one-time run finishes. A rejected
    request keeps the staged values so it can be retried as typed, but a run
    that ended on its own drops them (`finish_run`), so the UI returns to a
    blank form instead of looking like a pending request. An interrupt drops
    them the same way, via `reset`.
    """

    mode: str | None = None
    power: int | None = None
    duration: int | None = None
    # The staged values captured when the request was sent. A run that ends on
    # its own clears them only when nothing was edited meanwhile, so a request
    # typed during the run is not wiped.
    _sent: tuple[str | None, int | None, int | None] | None = None
    # Outcome of the last request. The device clears MI1 when the run ends, so
    # this is the only trace of what was actually sent. Only the send action
    # writes it, and editing an entity leaves it alone.
    last_sent_at: datetime | None = None
    last_error: str | None = None

    @property
    def signed_power(self) -> int | None:
        """Return what `MI1.power` should carry, sign included.

        Positive discharges, negative charges and zero means standby.
        Standby needs no power entity value, since it always sends zero.
        """
        if self.mode is None:
            return None
        if self.mode == LAKE6_MANUAL_MODE_STANDBY:
            return LAKE6_MANUAL_POWER_STANDBY
        if self.power is None:
            return None
        return LAKE6_MANUAL_MODE_TO_POWER_SIGN[self.mode] * self.power

    def reset(self) -> None:
        """Drop the staged request; `last_sent_at` keeps its history value."""
        self.mode = None
        self.power = None
        self.duration = None
        self._sent = None

    def mark_sent(self, staged: tuple[str | None, int | None, int | None]) -> None:
        """Record the staged values that started the running window."""
        self._sent = staged

    def finish_run(self) -> None:
        """Drop the staged request after the window ended on its own.

        Only when the staged values are still the ones that were sent:
        re-staging while the run lasted must survive the cleanup.
        """
        if (
            self._sent is not None
            and (self.mode, self.power, self.duration) == self._sent
        ):
            self.reset()


@dataclass
class Lake6Data:
    """Complete snapshot produced by one refresh."""

    energies: Lake6Energies
    alarms: Lake6Alarms
    modes: Lake6Modes
    control_panel: Lake6ControlPanel


@dataclass
class Lake6RuntimeData:
    """Runtime objects stored on the config entry."""

    coordinator: Lake6Coordinator
    device_id: str
    device: Lake6Device


# A single config entry carries either device generation and platforms
# dispatch with isinstance. The union leaves the EZ1 branch unchanged in both
# typing and runtime behaviour.
type ApSystemsConfigEntry = ConfigEntry[ApSystemsData | Lake6RuntimeData]

type Lake6ConfigEntry = ConfigEntry[Lake6RuntimeData]


class ApSystemsDataCoordinator(DataUpdateCoordinator[ApSystemsSensorData]):
    """Coordinator used for all sensors."""

    config_entry: ApSystemsConfigEntry
    device_version: str
    battery_system: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ApSystemsConfigEntry,
        api: APsystemsEZ1M,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="APSystems Data",
            update_interval=timedelta(seconds=12),
        )
        self.api = api

    @override
    async def _async_setup(self) -> None:
        try:
            device_info = await self.api.get_device_info()
        except ConnectionError, TimeoutError:
            raise UpdateFailed from None
        self.api.max_power = device_info.maxPower
        self.api.min_power = device_info.minPower
        self.device_version = device_info.devVer
        self.battery_system = device_info.isBatterySystem

    @override
    async def _async_update_data(self) -> ApSystemsSensorData:
        try:
            output_data = await self.api.get_output_data()
            alarm_info = await self.api.get_alarm_info()
        except InverterReturnedError:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="inverter_error"
            ) from None
        return ApSystemsSensorData(output_data=output_data, alarm_info=alarm_info)


class Lake6Coordinator(DataUpdateCoordinator[Lake6Data]):
    """Poll the Lake_6 endpoints on the schedule defined in §7."""

    config_entry: Lake6ConfigEntry

    device: Lake6Device

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: Lake6ConfigEntry,
        client: Lake6ApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="APsystems Lake_6",
            update_interval=timedelta(seconds=LAKE6_UPDATE_INTERVAL),
            # Every Lake6Data field is a frozen dataclass, so __eq__ is reliable.
            # Unchanged data then skips async_update_listeners, which avoids
            # rewriting entity states and recorder rows.
            always_update=False,
        )
        self.client = client
        self._modes: Lake6Modes | None = None
        self._modes_updated_at: float | None = None
        self._modes_dirty = False
        self._control_panel: Lake6ControlPanel | None = None
        self._control_panel_updated_at: float | None = None
        self.manual_control = Lake6ManualControl()
        # Apply, stop and the mode writes each put the device into a state that
        # the other one reads back, so they must not overlap.
        self._write_lock = asyncio.Lock()

    @override
    async def _async_setup(self) -> None:
        """Fetch the static device identity once."""
        # /devices is fetched on the first refresh only, then held by
        # Lake6RuntimeData.
        try:
            self.device = await self.client.async_get_device()
        except Lake6ApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="lake6_api_error"
            ) from err

    @override
    async def _async_update_data(self) -> Lake6Data:
        """Fetch every polled endpoint for one refresh cycle."""
        # /energies and /alarms share a cadence and run in sequence; a failure
        # of either fails the whole cycle.
        try:
            energies = await self.client.async_get_energies()
            alarms = await self.client.async_get_alarms()
            modes = await self._async_poll_modes()
            control_panel = await self._async_poll_control_panel()
        except Lake6ApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="lake6_api_error"
            ) from err
        return Lake6Data(
            energies=energies,
            alarms=alarms,
            modes=modes,
            control_panel=control_panel,
        )

    async def async_set_modes(self, **changes: Any) -> None:
        """Write /modes and re-read only that endpoint."""
        async with self._write_lock:
            # Mark the cache stale before the POST: a write the device accepted
            # but whose read-back failed must not be served from the cache for
            # the next five minutes.
            self._modes_dirty = True
            await self.client.async_set_modes(**changes)
            # Re-read /modes only. A full async_refresh() would also pull
            # /energies and /alarms, turning a few quick clicks into one POST
            # plus three GETs and pushing the device into timeouts.
            self._modes = await self.client.async_get_modes()
            self._modes_updated_at = monotonic()
            self._modes_dirty = False
            self._async_publish(
                Lake6Data(
                    energies=self.data.energies,
                    alarms=self.data.alarms,
                    modes=self._modes,
                    control_panel=self.data.control_panel,
                )
            )

    def _async_publish(self, data: Lake6Data) -> None:
        """Publish a partial update without restarting the poll timer.

        `async_set_updated_data` reschedules the coordinator refresh, so a
        steady stream of writes would keep pushing `/energies` and `/alarms`
        back and they would never be polled again.
        """
        self.data = data
        self.last_update_success = True
        self.async_update_listeners()

    async def async_set_manual_control(
        self,
        *,
        mode: str | None = None,
        power: int | None = None,
        duration: int | None = None,
    ) -> None:
        """Stage the changed fields without touching the device.

        The three entities can be filled in any order and any number of times;
        nothing is sent until `async_apply_manual_control` runs, so a half-typed
        request can never restart the window by accident.
        """
        control = self.manual_control
        if mode is not None:
            control.mode = mode
        if power is not None:
            control.power = power
        if duration is not None:
            control.duration = duration
        control.last_error = None
        self.async_update_listeners()

    async def async_apply_manual_control(self) -> None:
        """Send the staged request (§4.7), started by the button.

        Raises:
            ServiceValidationError: the staged request is incomplete, or the
                device answered the POST without entering the one-time run.
        """
        control = self.manual_control
        # Snapshot the staging before the first await: an edit made while the
        # request is in flight must not change what `mark_sent` records, or
        # `finish_run` would later clear a request that was never sent.
        staged = (control.mode, control.power, control.duration)
        signed_power = control.signed_power
        missing = [
            name
            for name, value in (
                ("mode", staged[0]),
                ("power", signed_power),
                ("duration", staged[2]),
            )
            if value is None
        ]
        if missing or signed_power is None or staged[2] is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="manual_control_incomplete",
                translation_placeholders={"fields": ", ".join(missing)},
            )
        try:
            await self._async_send_manual_control(
                power=signed_power, duration=staged[2], staged=staged
            )
        except Lake6ApiError as err:
            control.last_error = str(err)
            raise

    async def _async_send_manual_control(
        self,
        *,
        power: int,
        duration: int,
        staged: tuple[str | None, int | None, int | None],
    ) -> None:
        """Post a window that already started and verify the device took it.

        A well-formed request is dropped in silence in two cases: the timestamp
        width is not the one the firmware echoes, or the start is not behind the
        device's own clock. The window therefore begins
        `LAKE6_CONTROL_PANEL_START_BACKDATES` seconds ago while still ending
        `duration` minutes from now, so the run keeps its full length.

        The whole POST/settle/read-back transaction holds `_write_lock`, so an
        interrupt cannot land between a retry and be undone by the next one.
        """
        async with self._write_lock:
            # The device reads MI1.time as UTC, so a local time window is
            # dropped silently with code 200.
            now = dt_util.now(UTC)
            end = now + timedelta(minutes=duration)
            panel = Lake6ControlPanel(active=False, windows=[])
            for backdate in LAKE6_CONTROL_PANEL_START_BACKDATES:
                start = now - timedelta(seconds=backdate)
                for time_format in self._control_panel_time_formats():
                    await self.client.async_set_control_panel(
                        {
                            "mode": LAKE6_CONTROL_PANEL_MODE_ACTIVE,
                            "MI1": {
                                "time": [
                                    f"{start.strftime(time_format)}"
                                    f"{end.strftime(time_format)}"
                                ],
                                "power": [str(power)],
                            },
                        }
                    )
                    # A successful POST only means the payload was well formed;
                    # read back to confirm the device really entered a run.
                    await asyncio.sleep(LAKE6_CONTROL_PANEL_SETTLE)
                    panel = await self.client.async_get_control_panel()
                    if panel.active:
                        break
                    LOGGER.debug(
                        "Lake_6 ignored %s with a start %s s back, trying the next one",
                        time_format,
                        backdate,
                    )
                if panel.active:
                    break
            self._control_panel = panel
            self._control_panel_updated_at = monotonic()
            if panel.active:
                self.manual_control.mark_sent(staged)
            self.manual_control.last_sent_at = now
            self.manual_control.last_error = (
                None if panel.active else "device_not_running"
            )
            self._async_publish(
                Lake6Data(
                    energies=self.data.energies,
                    alarms=self.data.alarms,
                    modes=self.data.modes,
                    control_panel=panel,
                )
            )
        if not panel.active:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="manual_control_not_applied",
                translation_placeholders={
                    "power": str(power),
                    "duration": str(duration),
                },
            )

    async def async_interrupt_manual_control(self) -> None:
        """Clear the one-time run so the long-term mode takes over again.

        `mode="0"` takes an empty `MI1` (§4.7). The device answers a
        well-formed POST even when nothing changes, so the read-back decides
        whether the window really stopped.

        Raises:
            ServiceValidationError: the device still reports a running window.
        """
        async with self._write_lock:
            await self.client.async_set_control_panel(
                {"mode": LAKE6_CONTROL_PANEL_MODE_IDLE, "MI1": {}}
            )
            await asyncio.sleep(LAKE6_CONTROL_PANEL_SETTLE)
            panel = await self.client.async_get_control_panel()
            self._control_panel = panel
            self._control_panel_updated_at = monotonic()
            if not panel.active:
                # An interrupt withdraws the request, so the three staged
                # fields go as well; otherwise stale values would ride along
                # with the next send.
                self.manual_control.reset()
            self.manual_control.last_error = (
                None if not panel.active else "device_still_running"
            )
            self._async_publish(
                Lake6Data(
                    energies=self.data.energies,
                    alarms=self.data.alarms,
                    modes=self.data.modes,
                    control_panel=panel,
                )
            )
        if panel.active:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="manual_control_still_running",
            )

    def _control_panel_time_formats(self) -> list[str]:
        """Order the timestamp layouts by the one the device last echoed."""
        formats = list(LAKE6_CONTROL_PANEL_TIME_FORMATS)
        width = self._control_panel.timestamp_width if self._control_panel else None
        if width is not None and len(formats) > 1:
            # Sort by actual width instead of relying on the order in the
            # constant.
            formats.sort(
                key=lambda fmt: len(datetime(2000, 1, 1).strftime(fmt)) != width
            )
        return formats

    async def _async_poll_control_panel(self) -> Lake6ControlPanel:
        """Return the one-time run snapshot, throttled like `/modes`.

        The throttle is lifted while a window runs so the interrupt button
        greys out as soon as the device drops it; that same read is where a
        window ending on its own is noticed, and a finished run clears the
        staged request like an interrupt does.
        """
        now = monotonic()
        if (
            self._control_panel is not None
            and self._control_panel_updated_at is not None
            # No throttle while a one-time run is active: the window lasts only
            # minutes and the interrupt button has to grey out as soon as it ends.
            and not self._control_panel.active
            and now - self._control_panel_updated_at
            < LAKE6_CONTROL_PANEL_UPDATE_INTERVAL
        ):
            return self._control_panel
        was_active = self._control_panel.active if self._control_panel else False
        panel = await self.client.async_get_control_panel()
        self._control_panel = panel
        self._control_panel_updated_at = now
        if was_active and not panel.active:
            self.manual_control.finish_run()
        return panel

    async def _async_poll_modes(self) -> Lake6Modes:
        """Return the mode snapshot, honouring the 5-minute throttle."""
        now = monotonic()
        if (
            not self._modes_dirty
            and self._modes is not None
            and self._modes_updated_at is not None
            and now - self._modes_updated_at < LAKE6_MODES_UPDATE_INTERVAL
        ):
            return self._modes

        # On failure neither the timestamp nor the dirty flag is updated, so the
        # next cycle retries.
        modes = await self.client.async_get_modes()
        self._modes = modes
        self._modes_updated_at = now
        self._modes_dirty = False
        return modes
