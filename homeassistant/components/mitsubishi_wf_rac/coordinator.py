"""Data update coordinator for the Mitsubishi WF-RAC integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
import re
from typing import Any, override

from pywfrac import (
    MIN_TIME_BETWEEN_REQUESTS,
    REQUEST_TIMEOUT,
    Aircon,
    AirconCommands,
    FirmwareInfo,
    Repository,
    WfRacAccountTableFullError,
    WfRacConnectionError,
    WfRacError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_AIRCO_ID, DOMAIN, MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)

# Every request carries a full state block, so overlapping commands would send
# each other's fields back; commands inside this window go out as one.
UPDATE_CONSOLIDATION_PERIOD = timedelta(milliseconds=500)

# Covers both legs of protocol discovery; stays under MIN_TIME_BETWEEN_UPDATES.
POLL_TIMEOUT = 2 * REQUEST_TIMEOUT + MIN_TIME_BETWEEN_REQUESTS + timedelta(seconds=4)

# Tolerated failed polls before unavailable: the module reassociates WiFi about hourly
# and is unreachable for about a minute.
AVAILABILITY_FAILURE_LIMIT = 3


def registration_full_issue_id(entry_id: str) -> str:
    """Return the repair-issue id for a full account table."""
    return f"too_many_devices_{entry_id}"


@dataclass
class MitsubishiWfRacData:
    """Runtime data of a configured airco."""

    coordinator: WfRacCoordinator


type MitsubishiWfRacConfigEntry = ConfigEntry[MitsubishiWfRacData]


class WfRacCoordinator(DataUpdateCoordinator[Aircon]):
    """Polls one airco and sends it the commands of its entities."""

    config_entry: MitsubishiWfRacConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MitsubishiWfRacConfigEntry,
        repository: Repository,
    ) -> None:
        """Set up the coordinator for one airco."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self._repository = repository
        self._airco_id: str = config_entry.data[CONF_AIRCO_ID]
        self._firmware = FirmwareInfo()
        self._consecutive_failures = 0
        self._last_poll_error: BaseException | None = None
        # A command frame is built from self.data, so it must not overlap a poll.
        self._send_lock = asyncio.Lock()
        self._consolidated_params: dict[AirconCommands, Any] = {}
        self._consolidation_task: asyncio.Task[None] | None = None
        # _consolidation_task is only the flush still taking parameters.
        self._running_flushes: set[asyncio.Task[None]] = set()

    @override
    async def async_shutdown(self) -> None:
        """Cancel the queued flushes, which run outside the coordinator."""
        self._consolidation_task = None
        flushes = list(self._running_flushes)
        for flush in flushes:
            flush.cancel()
        await asyncio.gather(*flushes, return_exceptions=True)
        await super().async_shutdown()

    def _report_registration_full(self) -> None:
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            registration_full_issue_id(self.config_entry.entry_id),
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="too_many_devices",
            translation_placeholders={"device_name": self.name},
        )

    def _clear_registration_full_issue(self) -> None:
        ir.async_delete_issue(
            self.hass, DOMAIN, registration_full_issue_id(self.config_entry.entry_id)
        )

    def _command_failed(self, error: WfRacError) -> HomeAssistantError:
        # Notify listeners without marking the last poll as successful.
        self.async_update_listeners()
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"device": self.name, "error": str(error)},
        )

    async def _async_send(self, params: dict[AirconCommands, Any]) -> None:
        """Send one command frame and publish the unit's answer."""
        _LOGGER.debug("Setting airco: %s", params)
        # Held until the answer is published, or a second call reverts it.
        async with self._send_lock:
            try:
                aircon = await self._repository.async_send_command(
                    self._airco_id, self.data, params
                )
            except WfRacAccountTableFullError as ex:
                self._report_registration_full()
                raise self._command_failed(ex) from ex
            except WfRacError as ex:
                raise self._command_failed(ex) from ex
            except ValueError as ex:
                # The last read state holds a value that has no encoding.
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_unencodable",
                    translation_placeholders={"device": self.name},
                ) from ex
            # An accepted write proves the account is registered.
            self._clear_registration_full_issue()
            self._consecutive_failures = 0
            self.async_set_updated_data(aircon)

    async def async_queue_command(self, params: dict[AirconCommands, Any]) -> None:
        """Queue an airco command, merged with others in the consolidation window."""
        self._consolidated_params.update(params)
        if (flush := self._consolidation_task) is None:
            flush = self.hass.async_create_task(self._async_flush_queued_command())
            self._consolidation_task = flush
            self._running_flushes.add(flush)
            flush.add_done_callback(self._flush_done)
        # Not awaited directly: one caller giving up must not cancel the others'.
        try:
            await asyncio.wait({flush})
            flush.result()
        except asyncio.CancelledError:
            task = asyncio.current_task()
            # Our own cancellation must propagate.
            if task is not None and task.cancelling():
                raise
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_cancelled",
                translation_placeholders={"device": self.name},
            ) from None

    def _flush_done(self, flush: asyncio.Task[None]) -> None:
        self._running_flushes.discard(flush)
        # A flush nobody waits for any more would report its error as unretrieved.
        if not flush.cancelled():
            flush.exception()

    async def _async_flush_queued_command(self) -> None:
        await asyncio.sleep(UPDATE_CONSOLIDATION_PERIOD.total_seconds())
        params = self._consolidated_params.copy()
        self._consolidated_params.clear()
        self._consolidation_task = None
        await self._async_send(params)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device registry description.

        ModelNr is a capability grouping, not a type name, so it is model_id only.
        """
        info: DeviceInfo = {
            "sw_version": str(self._firmware),
            "identifiers": {(DOMAIN, self._airco_id)},
            "manufacturer": "Mitsubishi Heavy Industries",
            "name": self.name,
            "model_id": str(self.data.ModelNrRaw),
        }
        # Only a bare MAC is a connection; anything else would claim foreign hardware.
        if re.fullmatch(r"[0-9a-fA-F]{12}", self._airco_id):
            info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(self._airco_id))}
        return info

    @property
    def airco_id(self) -> str:
        """Return Airco ID."""
        return self._airco_id

    @property
    def connection_method(self) -> str | None:
        """Return the discovered communication method, if known."""
        return self._repository.method

    def _failed_poll(self, error: BaseException) -> Aircon:
        """Count a failed poll and fail the update once the limit is spent.

        The first poll has no earlier data to fall back on.
        """
        self._consecutive_failures = min(
            self._consecutive_failures + 1, AVAILABILITY_FAILURE_LIMIT
        )
        self._last_poll_error = error
        _LOGGER.debug("Could not reach the airco [%s]: %s", self.name, error)
        if (
            self.data is not None
            and self._consecutive_failures < AVAILABILITY_FAILURE_LIMIT
            and self.last_update_success
        ):
            return self.data
        raise self._update_failed(error)

    def _update_failed(self, error: BaseException) -> UpdateFailed:
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"device": self.name, "error": str(error)},
        )

    @override
    async def _async_update_data(self) -> Aircon:
        """Poll the unit."""
        if self._send_lock.locked():
            # The command publishes the answer itself and can outlast a poll.
            _LOGGER.debug(
                "Skipping the poll of [%s]: a command has the connection", self.name
            )
            # Standing down is no answer, so it cannot end a reported failure.
            if not self.last_update_success:
                raise self._update_failed(
                    self._last_poll_error
                    or WfRacConnectionError("no answer from the airco")
                )
            return self.data

        try:
            async with asyncio.timeout(POLL_TIMEOUT.total_seconds()):
                async with self._send_lock:
                    status = await self._repository.async_get_status(self._airco_id)
        except TimeoutError:
            # The outer deadline can expire before the repository's own attempts.
            return self._failed_poll(
                WfRacConnectionError(
                    f"did not answer within {POLL_TIMEOUT.total_seconds():.0f}s"
                )
            )
        except WfRacError as error:
            return self._failed_poll(error)

        self._consecutive_failures = 0
        self._firmware = status.firmware
        return status.aircon
