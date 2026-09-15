"""Device module."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
import re
import time
from typing import Any, override

from pywfrac import (
    Aircon,
    AirconCommands,
    AirconStat,
    RacParser,
    Repository,
    WfRacConnectionError,
    WfRacError,
    WfRacRegistrationError,
    WfRacWriteRefusedError,
)
from pywfrac.repository import MIN_TIME_BETWEEN_REQUESTS, REQUEST_TIMEOUT

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AC_CERT_FILENAME, DOMAIN, MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)

# Commands issued within this window are sent as one: every request carries a
# full state block, so two that overlap send each other's fields back.
UPDATE_CONSOLIDATION_PERIOD = timedelta(milliseconds=500)


# Both legs of protocol discovery: a unit that accepts a plaintext connection
# without answering spends the whole first one. Stays under
# MIN_TIME_BETWEEN_UPDATES so a slow poll cannot outlive its turn.
POLL_TIMEOUT = 2 * REQUEST_TIMEOUT + MIN_TIME_BETWEEN_REQUESTS + timedelta(seconds=4)

# Consecutive failed polls before the update fails, and the floor under the
# configurable value: the module reassociates to WiFi about once an hour and is
# gone for about a minute while it does.
AVAILABILITY_FAILURE_LIMIT_MIN = 3


def _revision(value: Any) -> str:
    """One firmware string of a status answer, or "unknown" where none came."""
    return str(value) if value else "unknown"


def _firmware_version(section: Any) -> str:
    """The firmVer of one section of a status answer, or "unknown"."""
    if not isinstance(section, dict):
        return "unknown"
    return _revision(section.get("firmVer"))


def result_code(answer: Any) -> int | None:
    """The result code of a module answer, or None if it carries none.

    The parsed body arrives as it came, so neither its shape nor the field's
    type is guaranteed.
    """
    if not isinstance(answer, dict):
        return None
    try:
        return int(answer["result"])
    except KeyError, TypeError, ValueError:
        return None


def registration_full_issue_id(entry_id: str) -> str:
    """Repair-issue id for a full account table on this entry's airco.

    Shared with async_remove_entry, which clears it when the entry is deleted.
    An unload leaves it standing: the condition outlives a reload.
    """
    return f"too_many_devices_{entry_id}"


# Fallback wait for a refused command, used where the remaining lock time
# cannot be established (see _async_write_lock_delay). One retry, not a loop.
WRITE_LOCK_RETRY_DELAY = timedelta(seconds=10)

# The lock runs 60 seconds, so a longer deadline came from a client whose clock
# is off. Above POLL_TIMEOUT on purpose - a poll that comes due meanwhile stands
# down rather than queue behind it (see _async_update_data).
WRITE_LOCK_MAX_WAIT = timedelta(seconds=61)


@dataclass
class MitsubishiWfRacData:
    """Runtime data of a configured airco."""

    device: Device


type MitsubishiWfRacConfigEntry = ConfigEntry[MitsubishiWfRacData]


class Device(DataUpdateCoordinator[Aircon]):
    """Device Class."""

    config_entry: MitsubishiWfRacConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MitsubishiWfRacConfigEntry,
        name: str,
        hostname: str,
        port: int,
        device_id: str,
        operator_id: str,
        airco_id: str,
        availability_failure_limit: int = AVAILABILITY_FAILURE_LIMIT_MIN,
        connection_method: str | None = None,
    ) -> None:
        """Set up the coordinator for one airco."""
        self._api = Repository(
            async_get_clientsession(hass),
            hostname,
            port,
            operator_id,
            device_id,
            method=connection_method,
            cert_path=hass.config.path(AC_CERT_FILENAME),
        )
        self._parser = RacParser()
        self._hass = hass

        self._airco = Aircon()
        self._operator_id = operator_id
        self._device_id = device_id
        self._host = hostname
        self._airco_id = airco_id
        self._name = name
        self._firmware = ""
        self._consecutive_failures = 0
        self._poll_counted = False
        self._last_poll_error: BaseException | None = None
        # Clamped, not validated: an entry can carry a lower value from an
        # older version, and refusing to load it over that helps nobody.
        self._availability_failure_limit = max(
            AVAILABILITY_FAILURE_LIMIT_MIN, availability_failure_limit
        )
        # Serializes a poll and a command end to end: a command frame is a
        # full state block built from self._airco, so one encoded from a
        # snapshot a poll is about to replace undoes that poll's news.
        self._send_lock = asyncio.Lock()
        self._consolidated_params: dict[AirconCommands, Any] = {}
        self._consolidation_task: asyncio.Task[None] | None = None
        # _consolidation_task is only the one still taking parameters.
        self._running_flushes: set[asyncio.Task[None]] = set()

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

    @property
    def entry_id(self) -> str:
        """Id of the config entry that owns this device."""
        return self.config_entry.entry_id

    @override
    async def async_shutdown(self) -> None:
        """Shut the coordinator down.

        The flushes run on hass rather than under DataUpdateCoordinator, so
        they are cancelled here: one that survived would publish to entities
        that are gone, and take the single connection the reload needs.
        """
        self._consolidation_task = None
        flushes = list(self._running_flushes)
        for flush in flushes:
            flush.cancel()
        # Accounted for elsewhere, and none may fail an unload.
        await asyncio.gather(*flushes, return_exceptions=True)
        await super().async_shutdown()

    async def update(self) -> bool:
        """Fetch one status block, and say whether the unit answered.

        Holds the send lock across the request and the state write, so a
        command cannot snapshot state this poll is about to replace.
        """
        async with self._send_lock:
            return await self._async_fetch_state()

    async def _async_fetch_state(self) -> bool:
        """Fetch and apply one status block. Caller holds the send lock."""
        try:
            response = await self._api.get_aircon_stats(self._airco_id)

        except WfRacConnectionError as ex:
            self._record_failed_poll(ex)
            return False
        except (WfRacError, KeyError) as ex:
            self._record_failed_poll(ex)
            # The official app can evict us from the module's small account
            # table, and polls fail until we register again. An evicted
            # account still answers - unlike the branch above.
            await self.add_account()
            return False

        try:
            self._airco = self._parser.translate_bytes(response["airconStat"])
            self._record_reachable()
        except (KeyError, TypeError, ValueError) as ex:
            self._record_failed_poll(ex)
            return False

        # Never allowed to fail the poll: revisions differ in which of these
        # sub-keys they send, and the strings only decorate the registry.
        self._firmware = (
            f"{_revision(response.get('firmType'))}, "
            f"mcu: {_firmware_version(response.get('mcu'))}, "
            f"wireless: {_firmware_version(response.get('wireless'))}"
        )

        return True

    def _encode_command(self, params: dict[AirconCommands, Any]) -> str:
        """Build the frame for a command.

        A full state block, not a delta: every field the caller did not name
        is sent back as we last saw it.
        """
        airco_stat = AirconStat.from_aircon(self._airco)
        for key, value in params.items():
            setattr(airco_stat, key, value)
        return self._parser.to_base64(airco_stat)

    async def _async_write_lock_delay(self) -> float:
        """Seconds to wait before retrying a write the unit just refused.

        The refusal carries no deadline and the last poll's `expires` is
        stale, so ask: a getAirconStat takes no lock of its own and reports
        when the one in the way lapses. It reads against our own clock, since
        the module takes its time from each request's `timestamp`.

        The answer is kept, not just its deadline: it carries what the other
        client wrote, which the retry's full block would hand straight back.
        """
        try:
            response = await self._api.get_aircon_stats(self._airco_id)
            self._airco = self._parser.translate_bytes(response["airconStat"])
            expires = response["expires"]
        except WfRacError, KeyError, TypeError, ValueError:
            return WRITE_LOCK_RETRY_DELAY.total_seconds()
        if not isinstance(expires, int):
            return WRITE_LOCK_RETRY_DELAY.total_seconds()
        # Whole seconds, refused while `expires` still equals the current one,
        # so land past the lapse. Epoch: a naive datetime is out when DST ends.
        remaining = expires - time.time() + 1
        return max(0.0, min(remaining, WRITE_LOCK_MAX_WAIT.total_seconds()))

    async def delete_account(self) -> dict[str, Any] | None:
        """Delete account (operator id) from the airco.

        None means the slot was not released - the request failed, or the
        answer did not confirm it. Nothing but a result code of 0 does: the
        refusal, the rate limit and the module's internal error all leave the
        slot where it was.
        """
        try:
            result = await self._api.del_account_info(self._airco_id)
        except WfRacError, KeyError, TypeError:
            _LOGGER.warning("Could not delete account from airco %s", self._airco_id)
            return None
        if result_code(result) != 0:
            return None
        return result

    async def add_account(self) -> dict[str, Any] | None:
        """Add account (operator id) from the airco."""
        try:
            result = await self._api.update_account_info(
                self._airco_id, self._hass.config.time_zone
            )
        except WfRacError, KeyError, TypeError:
            _LOGGER.debug("Could not add account from airco %s", self._airco_id)
            return None

        # Here result:2 means the account table is full, and nothing frees a
        # slot but the official app - a standing condition for Repairs, ended
        # by a registration that went through and by nothing else.
        code = result_code(result)
        if code == 2:
            self._report_registration_full()
        elif code == 0:
            self._clear_registration_full_issue()
        return result

    def _report_registration_full(self) -> None:
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            registration_full_issue_id(self.entry_id),
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="too_many_devices",
            translation_placeholders={"device_name": self.device_name},
        )

    def _clear_registration_full_issue(self) -> None:
        ir.async_delete_issue(
            self._hass, DOMAIN, registration_full_issue_id(self.entry_id)
        )

    async def set_airco(self, params: dict[AirconCommands, Any]) -> None:
        """Send one command frame to the airco."""
        _LOGGER.debug("Setting airco: %s", params)
        # Held across read-modify-send-update: a second call that snapshots
        # self._airco before this one's response lands reverts it.
        async with self._send_lock:
            try:
                self._airco = await self._send_command(params)
            except (WfRacError, KeyError, TypeError, ValueError) as ex:
                _LOGGER.warning("Could not send airco data: %s", str(ex))
                # The action awaits this, so hand it something showable.
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_failed",
                    translation_placeholders={
                        "device": self.device_name,
                        "error": str(ex),
                    },
                ) from ex
            # Proof of reachability like a poll: once a unit counts as away,
            # the service layer drops the calls that would show it is there.
            self._record_reachable()

    async def _send_command(self, params: dict[AirconCommands, Any]) -> Aircon:
        """Encode, send and read back one command frame.

        Separate from set_airco() so that its error handling wraps a single
        statement.
        """
        command = self._encode_command(params)
        try:
            response = await self._api.send_airco_command(self._airco_id, command)
        except WfRacWriteRefusedError:
            # Another client's 60-second write lock: the retry is placed
            # where it lapses, since one inside it is certain to be refused.
            await asyncio.sleep(await self._async_write_lock_delay())
            # Re-encoded: the wait refreshed the state, and a block built
            # before the refusal reverts what the other client wrote.
            response = await self._api.send_airco_command(
                self._airco_id, self._encode_command(params)
            )
        except WfRacRegistrationError:
            # Not in the account table: register again rather than lose the
            # command. A full table is already reported by add_account().
            await self.add_account()
            response = await self._api.send_airco_command(self._airco_id, command)

        return self._parser.translate_bytes(response)

    async def async_queue_command(self, params: dict[AirconCommands, Any]) -> None:
        """Queue an airco command, coalescing calls made close together.

        Calls within UPDATE_CONSOLIDATION_PERIOD become one set_airco(). Every
        entity uses this rather than set_airco(), so a fan change and a
        setpoint change issued together share a request instead of racing.
        """
        self._consolidated_params.update(params)
        if (flush := self._consolidation_task) is None:
            flush = self.hass.async_create_task(self._async_flush_queued_command())
            self._consolidation_task = flush
            self._running_flushes.add(flush)
            flush.add_done_callback(self._running_flushes.discard)
        # Awaited so a refusal reaches the action that caused it, shielded
        # because a caller giving up must not take the others' command.
        await asyncio.shield(flush)

    async def _async_flush_queued_command(self) -> None:
        await asyncio.sleep(UPDATE_CONSOLIDATION_PERIOD.total_seconds())
        params = self._consolidated_params.copy()
        self._consolidated_params.clear()
        # Parameters taken: anything queued from here needs its own window.
        self._consolidation_task = None
        try:
            await self.set_airco(params)
        except HomeAssistantError:
            # Already logged in set_airco(). A failed command says nothing
            # about the poll before it, so the listeners hear the state without
            # the coordinator being declared successful.
            self.async_update_listeners()
            raise
        # The unit's answer reaches the entities now, not a poll later.
        self.async_set_updated_data(self._airco)

    def _record_reachable(self) -> None:
        """Start the tolerance over, after the unit has answered."""
        self._consecutive_failures = 0

    def _record_failed_poll(self, error: BaseException) -> None:
        """Count one failed poll and keep what went wrong with it.

        Once per poll: the re-registration that follows a rejected answer is
        a second request under the same deadline. Saturated at the limit, and
        the error is kept for the poll that crosses it.
        """
        if self._poll_counted:
            return
        self._poll_counted = True
        self._consecutive_failures = min(
            self._consecutive_failures + 1, self._availability_failure_limit
        )
        self._last_poll_error = error
        _LOGGER.debug("Could not reach the airco [%s]: %s", self.device_name, error)

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry.

        No "model": ModelNr is a capability grouping (0/1/2/3/64...), not a
        type name, so it would put a bare digit where users expect
        "SRK35ZS-WF". It goes into model_id instead.
        """
        info: DeviceInfo = {
            "sw_version": self._firmware,
            "identifiers": {(DOMAIN, self.airco_id)},
            "manufacturer": "Mitsubishi Heavy Industries",
            "name": self.device_name,
        }
        # Claimed only when the id has exactly the shape of a bare MAC: a
        # different one would register as somebody else's hardware.
        if re.fullmatch(r"[0-9a-fA-F]{12}", self.airco_id):
            info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(self.airco_id))}
        model_nr = getattr(self.airco, "ModelNrRaw", None)
        if model_nr is not None:
            info["model_id"] = str(model_nr)
        return info

    @property
    def device_name(self) -> str:
        """Get given Airco name."""
        return self._name

    @property
    def airco_id(self) -> str:
        """Return Airco ID."""
        return self._airco_id

    @property
    def airco(self) -> Aircon:
        """Return parsed Aircon object if set otherwise None."""
        return self._airco

    @property
    def connection_method(self) -> str | None:
        """Return the discovered/persisted communication method (http/https), if known."""
        return self._api.method

    @override
    async def _async_update_data(self) -> Aircon:
        """Update data via library.

        One missed poll is not an update failure yet - the modules restart
        their WiFi about once an hour. A failure below the threshold returns
        the last data; a run of them fails the update.
        """
        if self._send_lock.locked():
            # A command holds the connection and publishes the unit's answer
            # itself, so this poll has nothing to add - and the write-lock
            # retry can hold it for longer than the whole poll budget.
            _LOGGER.debug(
                "Skipping the poll of [%s]: a command has the connection",
                self.device_name,
            )
            return self._airco

        # The poll starts here, not in update(): the count has to hold for
        # exactly one poll, whoever else calls that method.
        self._poll_counted = False
        try:
            async with asyncio.timeout(POLL_TIMEOUT.total_seconds()):
                answered = await self.update()
        except TimeoutError:
            # The outer deadline can expire before the repository's own
            # attempts do. That is a missed poll like any other.
            self._record_failed_poll(
                WfRacConnectionError(
                    f"did not answer within {POLL_TIMEOUT.total_seconds():.0f}s"
                )
            )
        except Exception as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "device": self.device_name,
                    "error": str(error),
                },
            ) from error
        else:
            if answered:
                return self._airco

        # Within tolerance and no failure reported yet. A reported one ends
        # when a poll answers, not on the next routine dropout.
        if (
            self._consecutive_failures < self._availability_failure_limit
            and self.last_update_success
        ):
            return self._airco
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={
                "device": self.device_name,
                "error": str(self._last_poll_error),
            },
        )
