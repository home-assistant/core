"""DataUpdateCoordinator for the Adax component."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, cast, override

from adax import RATE_LIMIT_SECONDS, Adax
from adax_local import Adax as AdaxLocal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ACCOUNT_ID,
    COMMAND_TIMEOUT,
    DOMAIN,
    SCAN_INTERVAL,
    STALE_DATA_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# One second more than the client's rate limit, so its check has passed.
RATE_LIMIT_WINDOW = timedelta(seconds=RATE_LIMIT_SECONDS + 1)


type AdaxConfigEntry = ConfigEntry[AdaxCloudCoordinator | AdaxLocalCoordinator]


@dataclass(slots=True)
class _Command:
    """A command for one room, waiting to be sent."""

    temperature: float
    heating_enabled: bool
    # Set to the outcome: "sent", "superseded", "not_accepted" or "timeout".
    outcome: asyncio.Future[str]


class AdaxCloudCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator for updating data to and from Adax (cloud).

    The client allows one request per RATE_LIMIT_SECONDS. A request inside
    that window is refused without an error: a poll then gets the old data
    back and a command can hang. So every request goes through this
    coordinator, one at a time, and waits until the window has passed.
    """

    config_entry: AdaxConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AdaxConfigEntry) -> None:
        """Initialize the Adax coordinator used for Cloud mode."""
        super().__init__(
            hass,
            config_entry=entry,
            logger=_LOGGER,
            name="AdaxCloud",
            update_interval=SCAN_INTERVAL,
        )
        self._account_id = entry.data[ACCOUNT_ID]
        self._password = entry.data[CONF_PASSWORD]
        self.adax_data_handler = self._create_data_handler()
        self._client_created = dt_util.utcnow()
        # The room list from the last poll that brought new data, and when.
        self._last_rooms: list[dict[str, Any]] | None = None
        self._last_new_data: datetime | None = None
        # Held for every request to the client.
        self._client_lock = asyncio.Lock()
        self._last_request = dt_util.utcnow() - RATE_LIMIT_WINDOW
        # Commands not sent yet (the latest one per room), and being sent.
        self._pending: dict[str, _Command] = {}
        self._sending: dict[str, _Command] = {}

    def _create_data_handler(self) -> Adax:
        """Create a client for the Adax cloud API."""
        return Adax(
            self._account_id,
            self._password,
            websession=async_get_clientsession(self.hass),
        )

    def _replace_data_handler(self) -> None:
        """Start again with a new client, which logs in again."""
        self.adax_data_handler = self._create_data_handler()
        self._client_created = dt_util.utcnow()
        self._last_rooms = None

    async def _async_wait_for_client(self) -> None:
        """Wait until the client allows a request. Hold the client lock."""
        wait = (
            self._last_request + RATE_LIMIT_WINDOW - dt_util.utcnow()
        ).total_seconds()
        if wait > 0:
            await asyncio.sleep(wait)

    @override
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from the Adax."""
        async with self._client_lock:
            await self._async_wait_for_client()
            if self._pending:
                # Commands that came while this poll waited go first.
                await self._async_send_pending()
                await self._async_wait_for_client()
            try:
                rooms = await self.adax_data_handler.fetch_rooms_info() or []
                _LOGGER.debug("fetch_rooms_info returned: %s", rooms)
                new_data = bool(rooms)
                if not rooms:
                    # adax 0.4.0's fetch_rooms_info() returns None and keeps
                    # the rooms in the client, where get_rooms() returns them
                    # without another request. The client swaps in a new list
                    # only when a response was parsed. If not (for example on
                    # an empty response) it logs nothing and get_rooms()
                    # returns the old list. So the same list object as last
                    # time means no new data. Identity, not equality: new data
                    # can have the same values.
                    rooms = await self.adax_data_handler.get_rooms() or []
                    _LOGGER.debug("get_rooms returned: %s", rooms)
                    new_data = bool(rooms) and rooms is not self._last_rooms
            except OSError as e:
                raise UpdateFailed(f"Error communicating with API: {e}") from e
            finally:
                self._last_request = dt_util.utcnow()

        now = dt_util.utcnow()
        if new_data:
            self._last_rooms = rooms
            self._last_new_data = now
            # Copy the rooms. The client changes its own copies in place when a
            # command is sent, and that must not show up as data from the cloud.
            return {
                room["id"]: {**room, "energyWh": int(room.get("energyWh", 0))}
                for room in rooms
            }

        if (
            self.data is not None
            and self._last_new_data is not None
            and now - self._last_new_data < STALE_DATA_TIMEOUT
        ):
            return self.data

        if now - self._client_created >= STALE_DATA_TIMEOUT:
            # Reloading the config entry was the only way out of this before.
            # Do what it does.
            _LOGGER.debug("No new data from Adax, creating a new client")
            self._replace_data_handler()

        raise UpdateFailed("No new data from the Adax cloud")

    async def async_set_room_target_temperature(
        self, room_id: str, temperature: float, heating_enabled: bool
    ) -> None:
        """Send a command for one room and show it until the next new data."""
        command = _Command(
            float(temperature),
            heating_enabled,
            self.hass.loop.create_future(),
        )
        if (previous := self._pending.get(room_id)) is not None:
            previous.outcome.set_result("superseded")
        self._pending[room_id] = command
        # Send from a task of its own, so the command is still sent if the
        # caller is cancelled (an automation restarting, for example). Every
        # way that task ends sets the outcome.
        self.config_entry.async_create_background_task(
            self.hass, self._async_send_pending_when_free(), "adax send commands"
        )
        outcome = await asyncio.shield(command.outcome)
        if outcome == "timeout":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_timeout",
                translation_placeholders={"room": self._room_name(room_id)},
            )
        if outcome == "not_accepted":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"room": self._room_name(room_id)},
            )

    async def _async_send_pending_when_free(self) -> None:
        """Send the pending commands once no other request is running."""
        try:
            async with self._client_lock:
                if self._pending:
                    await self._async_send_pending()
        except asyncio.CancelledError:
            # Unloading: tell the callers instead of leaving them waiting.
            for command in (*self._sending.values(), *self._pending.values()):
                self._set_outcome(command, "timeout")
            raise

    async def _async_send_pending(self) -> None:
        """Send all pending commands in one go. Hold the client lock."""
        # Let commands from the same service call, and any that come while
        # the client is busy, join this batch.
        await asyncio.sleep(0)
        await self._async_wait_for_client()
        commands = self._sending = self._pending
        self._pending = {}
        client = self.adax_data_handler
        try:
            async with asyncio.timeout(COMMAND_TIMEOUT):
                # Sent together, the client merges them into one request.
                await asyncio.gather(
                    *(
                        client.set_room_target_temperature(
                            room_id, command.temperature, command.heating_enabled
                        )
                        for room_id, command in commands.items()
                    )
                )
                # adax 0.4.0 returns normally even when the cloud refused a
                # command, but it only changes its own copy of a room when the
                # cloud took it. Read those copies; this makes no request.
                client_rooms = {
                    room["id"]: room for room in await client.get_rooms() or []
                }
        except TimeoutError:
            # adax 0.4.0 can wait for ever on a failed request.
            self._fail_batch(commands, "timeout")
            return
        except Exception:
            _LOGGER.exception("Error sending commands to Adax")
            self._fail_batch(commands, "not_accepted")
            return
        finally:
            self._last_request = dt_util.utcnow()

        data = dict(self.data or {})
        for room_id, command in commands.items():
            client_room = client_rooms.get(room_id)
            if client_room is None:
                # A new client has no rooms until its first fetch, so it
                # cannot tell whether the cloud took the command. Leave the
                # state to the next poll.
                self._set_outcome(command, "sent")
                continue
            if client_room.get("heatingEnabled") != command.heating_enabled or (
                client_room.get("targetTemperature")
                != int(command.temperature * 100) / 100
            ):
                self._set_outcome(command, "not_accepted")
                continue
            self._set_outcome(command, "sent")
            # The client cannot fetch for 30 s after a command, so show the
            # command now. The next poll with new data replaces it with what
            # the cloud says.
            if (room := data.get(room_id)) is not None:
                data[room_id] = {
                    **room,
                    "targetTemperature": command.temperature,
                    "heatingEnabled": command.heating_enabled,
                }
        self._sending = {}
        if self.data is not None:
            self.data = data
            self.async_update_listeners()

    def _fail_batch(self, commands: dict[str, _Command], outcome: str) -> None:
        """Fail the batch being sent, and start again with a new client.

        Commands queued since the batch was taken are sent with the new
        client by their own tasks. The old client may still send the batch,
        or be left broken, so it is not used again.
        """
        for command in commands.values():
            self._set_outcome(command, outcome)
        self._sending = {}
        self._replace_data_handler()

    @staticmethod
    def _set_outcome(command: _Command, outcome: str) -> None:
        """Set a command's outcome unless it already has one."""
        if not command.outcome.done():
            command.outcome.set_result(outcome)

    def _room_name(self, room_id: str) -> str:
        """Return the room's name for messages."""
        return str((self.data or {}).get(room_id, {}).get("name", room_id))


class AdaxLocalCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator for updating data to and from Adax (local)."""

    def __init__(self, hass: HomeAssistant, entry: AdaxConfigEntry) -> None:
        """Initialize the Adax coordinator used for Local mode."""
        super().__init__(
            hass,
            config_entry=entry,
            logger=_LOGGER,
            name="AdaxLocal",
            update_interval=SCAN_INTERVAL,
        )

        self.adax_data_handler = AdaxLocal(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_TOKEN],
            websession=async_get_clientsession(hass, verify_ssl=False),
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Adax."""
        if result := await self.adax_data_handler.get_status():
            return cast(dict[str, Any], result)
        raise UpdateFailed("Got invalid status from device")
