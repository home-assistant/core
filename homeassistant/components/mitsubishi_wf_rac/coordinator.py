"""Device module."""

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
import re
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

# Commands issued within this window of each other (from any entity) are
# coalesced into a single set_airco() call instead of being sent as separate
# requests. The unit expects a full state block per request, so two
# near-simultaneous separate commands can otherwise overwrite each other
# instead of merging (e.g. a fan-speed change followed shortly by a
# temperature change loses the fan change).
UPDATE_CONSOLIDATION_PERIOD = timedelta(milliseconds=500)


# Room for both legs of protocol discovery plus the minimum spacing between
# requests, so a poll that has to fall back to the other protocol is not
# cancelled halfway through.
#
# Sized as more than a single per-request timeout: a unit that accepts a
# plaintext connection without answering it consumes the whole window on the
# first leg, so an equal-sized budget would never reach the second leg. A
# unit that only speaks the second protocol would then fail every poll the
# same way and never recover on its own.
#
# Stays under MIN_TIME_BETWEEN_UPDATES so a slow poll cannot still be running
# when the next one is due.
POLL_TIMEOUT = 2 * REQUEST_TIMEOUT + MIN_TIME_BETWEEN_REQUESTS + timedelta(seconds=4)

# Consecutive failed polls before the device is reported unavailable, and the
# floor under the configurable value. The module reassociates to WiFi about
# once an hour and is unreachable while it does (see the README's
# Troubleshooting section); reporting that as an outage every time is noise.
# Three polls at MIN_TIME_BETWEEN_UPDATES is roughly three minutes of grace,
# which rides through the reassociation without hiding a device that is
# genuinely gone. Raising it is a legitimate choice on a weak link; lowering it
# only ever produced the phantom outages this floor exists to prevent.
AVAILABILITY_FAILURE_LIMIT_MIN = 3


def registration_full_issue_id(entry_id: str) -> str:
    """Repair-issue id for a full account table on this entry's airco.

    Shared between Device (which raises/clears it) and async_unload_entry
    (which clears it on removal, so a deleted entry doesn't leave a dangling
    issue behind) - one format, so the two can never drift apart.
    """
    return f"too_many_devices_{entry_id}"


# One retry for a user command refused because someone else holds the lock,
# timed to land just after the lock lapses (see _async_write_lock_delay). Used
# as-is only when the remaining lock time cannot be established, where a short
# retry is still worth more than none: the common case is an app action already
# most of the way through its 60s. A retry that still fails is reported rather
# than repeated - two clients are genuinely fighting over the unit at that
# point.
WRITE_LOCK_RETRY_DELAY = timedelta(seconds=10)

# The lock runs 60 seconds, so a longer wait than that means the deadline was
# stamped by a client whose clock is off rather than that the lock is really
# still running - cap it instead of leaving a service call hanging on someone
# else's clock. See _async_write_lock_delay().
WRITE_LOCK_MAX_WAIT = timedelta(seconds=61)


class Device(DataUpdateCoordinator[Aircon]):  # pylint: disable=too-many-instance-attributes
    """Device Class."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
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

        # Protected state
        self._airco = Aircon()
        self._operator_id = operator_id
        self._device_id = device_id
        self._host = hostname
        self._port = port
        self._airco_id = airco_id
        self._available = False
        self._name = name
        self._firmware = ""
        self._connected_accounts = -1
        self._updated_by: str | None = None
        self._account_expires: int | None = None
        self._led_status: int | None = None
        self._auto_heating: int | None = None
        self._consecutive_failures = 0
        # Clamped rather than validated: an entry can carry a lower value from
        # an older version, and refusing to set up over it would be worse than
        # quietly giving it the tolerance it should have had.
        self._availability_failure_limit = max(
            AVAILABILITY_FAILURE_LIMIT_MIN, availability_failure_limit
        )
        # Serializes set_airco() calls end-to-end (snapshot build through
        # self._airco update) so a call can never build its diff from a
        # snapshot that's stale because another set_airco() is still in
        # flight - see set_airco() below.
        self._send_lock = asyncio.Lock()
        self._consolidated_params: dict[AirconCommands, Any] = {}
        self._consolidation_task: asyncio.Task[None] | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

    @property
    def options(self) -> Mapping[str, Any]:
        """Options of the config entry that owns this device.

        DataUpdateCoordinator.config_entry is typed as optional because a
        coordinator need not have one - this integration always constructs a
        Device with one, passed to super().__init__() above.
        """
        assert self.config_entry is not None
        return self.config_entry.options

    @property
    def entry_id(self) -> str:
        """Id of the config entry that owns this device - see options above."""
        assert self.config_entry is not None
        return self.config_entry.entry_id

    @override
    async def async_shutdown(self) -> None:
        """Shut the coordinator down."""
        await super().async_shutdown()

    async def update(self) -> bool:
        """Update the device information from API.

        Called both directly (initial fetch in __init__.py before entities
        exist, and set_airco()'s own fallback fetch) and by the coordinator
        via _async_update_data() below. Deliberately does not call
        async_refresh()/async_set_updated_data() itself: on the coordinator
        poll path, listeners are already notified automatically once
        _async_update_data() returns, and calling async_refresh() here would
        re-enter _async_update_data() -> update() from within that same path.
        The other two call sites don't need a notification either - the
        initial fetch runs before any entity/listener exists, and
        set_airco()'s fallback fetch is immediately followed by a command
        whose completion already triggers async_set_updated_data() (see
        Device.async_queue_command()).
        """

        try:
            response = await self._api.get_aircon_stats(self._airco_id)

        except WfRacConnectionError as ex:
            self._record_connection_failure(ex)
            return False
        except (WfRacError, KeyError) as ex:
            self._set_availability(False)
            _LOGGER.warning(
                "Error: something went wrong updating the airco [%s] values",
                self.device_name,
                exc_info=ex,
            )
            # The WF-RAC module keeps only a small, fixed-size table of registered
            # accounts (operator ids). Opening the official app or adding phones can
            # silently evict Home Assistant from that table, after which polls fail
            # until the integration is reloaded. Proactively re-register our account
            # on failure so we recover automatically on the next poll if we were
            # evicted. An evicted account still answers (HTTP 400 / result:2, see
            # Repository.get_aircon_stats), so this is skipped above when the unit
            # was simply unreachable - re-registering can't succeed over a
            # connection that isn't there. add_account() swallows its own errors.
            await self.add_account()
            return False

        try:
            self._connected_accounts = int(response["numOfAccount"])
            new_airco = self._parser.translate_bytes(response["airconStat"])
            self._carry_forward_home_leave_mode(new_airco)
            self._airco = new_airco
            # Not part of the airconStat blob, present alongside it in the same
            # response. Tolerate absence (.get()) since it's undocumented and
            # could be missing on older firmware.
            self._updated_by = response.get("updatedBy")
            self._account_expires = response.get("expires")
            self._led_status = response.get("ledStat")
            self._auto_heating = response.get("autoHeating")
            became_available = self._set_availability(True)
            if became_available:
                _LOGGER.info("Airco [%s] is available again", self.device_name)
        except (KeyError, TypeError, ValueError) as ex:
            _LOGGER.warning("Could not parse airco data", exc_info=ex)
            self._set_availability(False)
            return False

        # Cosmetic (diagnostic sensor only). Some firmware revisions omit the
        # "mcu"/"wireless" sub-keys entirely, so their versions are optional
        # and fall back to "unknown" instead of failing the update.
        firm_type = response.get("firmType", "unknown")
        mcu_ver = (response.get("mcu") or {}).get("firmVer", "unknown")
        wireless_ver = (response.get("wireless") or {}).get("firmVer", "unknown")
        self._firmware = f"{firm_type}, mcu: {mcu_ver}, wireless: {wireless_ver}"

        return True

    async def _async_write_lock_delay(self) -> float:
        """Seconds to wait before retrying a write the unit just refused.

        The refusal carries no deadline with it, and the `expires` from the
        last poll is our own stale one - the lock in the way was taken after
        that poll, which is why we did not see it coming. So ask: a
        getAirconStat is cheap and takes no lock of its own, and it reports
        when the lock currently held lapses.

        That deadline can be read against our own clock directly, because the
        module has none: it takes its time from the `timestamp` field of every
        request it receives, so the request asking the question sets the clock
        the answer is measured against. What that cannot fix is a deadline
        stamped by a client whose own clock was off - hence the cap.

        Falls back to WRITE_LOCK_RETRY_DELAY when the unit does not answer or
        reports no `expires` at all.
        """
        try:
            response = await self._api.get_aircon_stats(self._airco_id)
            expires = response["expires"]
        except WfRacError, KeyError, TypeError, ValueError:
            return WRITE_LOCK_RETRY_DELAY.total_seconds()
        if not isinstance(expires, int):
            return WRITE_LOCK_RETRY_DELAY.total_seconds()
        # The module compares whole seconds and refuses while `expires` still
        # equals the current one, so land on the far side of the lapse.
        remaining = expires - datetime.now().timestamp() + 1
        return max(0.0, min(remaining, WRITE_LOCK_MAX_WAIT.total_seconds()))

    async def delete_account(self) -> dict[str, Any] | None:
        """Delete account (operator id) from the airco."""
        try:
            return await self._api.del_account_info(self._airco_id)
        except WfRacError, KeyError, TypeError:
            _LOGGER.warning("Could not delete account from airco %s", self._airco_id)
            return None

    async def add_account(self) -> dict[str, Any] | None:
        """Add account (operator id) from the airco."""
        try:
            result = await self._api.update_account_info(
                self._airco_id, self._hass.config.time_zone
            )
        except WfRacError, KeyError, TypeError:
            _LOGGER.warning("Could not add account from airco %s", self._airco_id)
            return None

        # On updateAccountInfo specifically, result:2 does mean the account
        # table is full: the module answers it when no slot matches our id and
        # none is free. (The same code means other things on setAirconStat -
        # see RESULT_CODES - but this endpoint never talks to the indoor unit,
        # so those paths cannot reach it here.)
        #
        # Nothing frees a slot on its own: registrations do not expire and are
        # never evicted, so re-registering cannot succeed until someone
        # removes one from the official app - or the module is set up afresh.
        # That is a standing condition worth a repair issue rather than a
        # warning that scrolls out of the log every cycle; a normal-looking
        # response means whatever caused it is gone, so the issue (if any)
        # clears itself.
        if result and int(result.get("result", 0)) == 2:
            self._report_registration_full()
        else:
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
        # Held for the whole read-modify-send-update sequence, not just the
        # send: the snapshot below must only ever be built from self._airco
        # once no other set_airco() call is still in flight, otherwise a
        # queued command (see async_queue_command()) could snapshot state
        # from before a concurrent call's response landed and, once sent,
        # silently revert whatever that call had just changed.
        async with self._send_lock:
            airco_stat = AirconStat.from_aircon(self._airco)

            for key, value in params.items():
                setattr(airco_stat, key, value)

            try:
                command = self._parser.to_base64(airco_stat)
                try:
                    response = await self._api.send_airco_command(
                        self._airco_id, command
                    )
                except WfRacWriteRefusedError:
                    # Most likely another client's 60-second write lock - the
                    # Smart M-Air app was used moments ago (#294). Waiting it
                    # out is the only thing that helps: our registration is
                    # fine, so re-registering would just cost a request. One
                    # retry, placed where the lock lapses rather than at a
                    # guessed interval - a retry that lands inside the same
                    # lock is a request spent on a refusal that was certain.
                    await asyncio.sleep(await self._async_write_lock_delay())
                    response = await self._api.send_airco_command(
                        self._airco_id, command
                    )
                except WfRacRegistrationError:
                    # Our operator id is not in the airco's account table.
                    # Re-register and try once more rather than losing the
                    # command outright. If the table is full instead,
                    # add_account() has already raised the repair issue.
                    await self.add_account()
                    response = await self._api.send_airco_command(
                        self._airco_id, command
                    )
                new_airco = self._parser.translate_bytes(response)
                self._carry_forward_home_leave_mode(new_airco)
                self._airco = new_airco
            except (WfRacError, KeyError, TypeError, ValueError) as ex:
                _LOGGER.warning("Could not send airco data: %s", str(ex))
                raise

    async def async_queue_command(self, params: dict[AirconCommands, Any]) -> None:
        """Queue an airco command, coalescing calls made close together.

        Calls within UPDATE_CONSOLIDATION_PERIOD become a single set_airco()
        call. Used by all
        entities instead of calling set_airco() directly, so that e.g. a fan
        speed change and a temperature change issued moments apart end up in
        the same request instead of racing each other.
        """
        self._consolidated_params.update(params)
        if self._consolidation_task is None:
            self._consolidation_task = self.hass.async_create_task(
                self._async_flush_queued_command()
            )

    def _carry_forward_home_leave_mode(self, new_airco: Aircon) -> None:
        """Carry the HomeLeaveMode segment forward across updates.

        The unit reports the Tag-248 extension segment exactly once per
        HomeLeaveModeStatusRequest, then stops: the bridge MCU clears
        its response cache after handing it to the WiFi side, so the segment is
        present in a short window's worth of status blocks and absent from every
        later poll. Observed effect: translate_bytes() builds a fresh Aircon()
        with both fields back at their None default, which made the diagnostic
        sensors flash the real value for one update cycle and then revert to
        unknown. Carry the last known reading forward instead so it survives
        until the next explicit request or a fresh None response (e.g.
        reconnect).
        """
        if new_airco.HomeLeaveModeForCooling is None:
            new_airco.HomeLeaveModeForCooling = self._airco.HomeLeaveModeForCooling
        if new_airco.HomeLeaveModeForHeating is None:
            new_airco.HomeLeaveModeForHeating = self._airco.HomeLeaveModeForHeating

    async def _async_flush_queued_command(self) -> None:
        await asyncio.sleep(UPDATE_CONSOLIDATION_PERIOD.total_seconds())
        params = self._consolidated_params.copy()
        self._consolidated_params.clear()
        self._consolidation_task = None
        try:  # noqa: SIM105
            await self.set_airco(params)
        except WfRacError, KeyError, TypeError, ValueError:
            # Already logged in set_airco(). This runs as a detached task
            # (nothing awaits it), so without this the re-raised error becomes
            # an orphaned "Task exception was never retrieved" with zero
            # HA-visible feedback that the command never reached the unit.
            # Still notify below so entities pick up self.available if the
            # same failure already flipped it.
            pass
        # Immediately push the (possibly unchanged, on failure) state to all
        # entities instead of leaving them to wait for the next poll (up to
        # MIN_TIME_BETWEEN_UPDATES later).
        self.async_set_updated_data(self._airco)

    def _set_availability(self, available: bool) -> bool:
        """Record one poll result and update the availability flag.

        Return True only when the failure threshold is first reached or a
        later successful poll recovers from that threshold. Keeping the
        counter saturated while offline prevents a long outage from looking
        like a new transition every few polls.
        """
        if available:
            became_available = (
                self._consecutive_failures >= self._availability_failure_limit
            )
            self._consecutive_failures = 0
            self._available = True
            return became_available

        previous_failures = self._consecutive_failures
        self._consecutive_failures = min(
            previous_failures + 1, self._availability_failure_limit
        )
        if self._consecutive_failures >= self._availability_failure_limit:
            self._available = False
        return (
            previous_failures
            < self._availability_failure_limit
            <= self._consecutive_failures
        )

    def _record_connection_failure(self, error: BaseException) -> None:
        """Count one failed poll, and log it at the level it deserves.

        Every poll still reaches entities (_async_update_data returns the last
        data on an expected failure), so crossing the threshold needs no
        notification of its own - only the line that says it happened.
        """
        became_unavailable = self._set_availability(False)
        if became_unavailable:
            _LOGGER.warning(
                "Airco [%s] is unavailable after %s failed polls",
                self.device_name,
                self._availability_failure_limit,
            )
            _LOGGER.debug("Update of [%s] failed", self.device_name, exc_info=error)
        else:
            _LOGGER.debug("Could not reach the airco [%s]: %s", self.device_name, error)

    def set_available(self, available: bool) -> None:
        """Set available status."""
        self._set_availability(available)

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry.

        No "model": the only model field the protocol offers is ModelNr, a
        capability grouping (0/1/2/3/64...), not a type name - it would put a
        bare digit where users expect "SRK35ZS-WF". It goes into model_id
        instead, which is what a machine-readable model identifier is for, and
        stays available as its own diagnostic sensor.
        """
        info: DeviceInfo = {
            "sw_version": self._firmware,
            "identifiers": {(DOMAIN, self.airco_id)},
            "manufacturer": "Mitsubishi (WF-RAC)",
            "name": self.device_name,
        }
        # airconId is MAC-derived, and on every module seen so far it is the
        # bare MAC. Only claim it when it has exactly that shape - a differently
        # shaped id would otherwise register as somebody else's hardware and
        # merge two unrelated devices in the registry.
        if re.fullmatch(r"[0-9a-fA-F]{12}", self.airco_id):
            info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(self.airco_id))}
        model_nr = getattr(self.airco, "ModelNrRaw", None)
        if model_nr is not None:
            info["model_id"] = str(model_nr)
        return info

    @property
    def operator_id(self) -> str:
        """Return Airco Operator ID."""
        return self._operator_id

    @property
    def num_accounts(self) -> int:
        """Return Accounts connected."""
        return self._connected_accounts

    @property
    def updated_by(self) -> str | None:
        """Return what last updated the airco's state ('local' or a foreign account)."""
        return self._updated_by

    @property
    def account_expires(self) -> int | None:
        """Return the raw 'expires' timestamp reported alongside our account registration."""
        return self._account_expires

    @property
    def led_status(self) -> int | None:
        """Return the airco's front panel LED status."""
        return self._led_status

    @property
    def auto_heating(self) -> int | None:
        """Return the airco's auto-heating flag."""
        return self._auto_heating

    @property
    def device_id(self) -> str:
        """Return Airco device ID."""
        return self._device_id

    @property
    def host(self) -> str:
        """Get Host (IP)."""
        return self._host

    @property
    def port(self) -> int:
        """Get Port."""
        return self._port

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
    def available(self) -> bool:
        """Return True if device is available."""
        return self._available

    @property
    def connection_method(self) -> str | None:
        """Return the discovered/persisted communication method (http/https), if known."""
        return self._api.method

    @property
    def result_codes(self) -> dict[str, dict[str, int]]:
        """How often the unit refused each command, per `result` code.

        Refusals themselves are a debug-level event: the common ones clear on
        the next request and there is nothing for a user to do. Surfacing the
        tally here keeps them available to whoever is actually investigating.
        """
        return self._api.result_codes

    @override
    async def _async_update_data(self) -> Aircon:
        """Update data via library.

        A missed poll is not an update failure. These modules restart their
        WiFi about once an hour on their own, so single failures are routine
        and carry no consequence: _set_availability() rides them out, and
        entities follow Device.available rather than the coordinator's own
        success flag. Raising UpdateFailed for one would put an error in every
        user's log once an hour for a condition nobody can act on - and the
        entities would flick to unavailable a poll before our own threshold
        says they should. So an expected failure returns the last data instead,
        and only the availability transition is worth a line.
        """
        try:
            async with asyncio.timeout(POLL_TIMEOUT.total_seconds()):
                await self.update()
        except TimeoutError:
            # The outer deadline can expire before the repository's individual
            # connection attempts do. Treat that exactly like any other missed
            # poll so transient outages stay quiet and the entity only becomes
            # unavailable at the configured threshold.
            self._record_connection_failure(
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

        return self._airco
