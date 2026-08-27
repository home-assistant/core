"""Keeps a live connection to the CoolBot cloud and publishes state to entities."""

import logging
from typing import override

from pycoolbot import CoolbotAuthError, CoolbotClient, CoolbotDevice, CoolbotError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STALE_AFTER_SECONDS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type CoolbotConfigEntry = ConfigEntry[CoolbotCoordinator]


class CoolbotCoordinator(DataUpdateCoordinator[dict[str, CoolbotDevice]]):
    """Maintains one socket to the CoolBot cloud for a config entry.

    The cloud pushes readings continuously, so this does not poll the service. It
    reads the client's already-received state on a short interval and hands it to
    entities, which also serves as the keepalive.

    Reconnection is handled here rather than in the library: a CoolBot drops off
    and returns every few minutes, and the socket does not always survive that.
    """

    config_entry: CoolbotConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CoolbotConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self._client: CoolbotClient | None = None
        #: Last known name and reporting state per device, keyed by unique id;
        #: absent until a device first reports. The name is kept so a device
        #: that drops out of the profile can still be named in a log line.
        self._reporting: dict[str, tuple[str, bool]] = {}
        #: Devices that already have entities, so each refresh only adds coolers
        #: that are new. Held here rather than in the platform so a removal can
        #: clear it.
        self.known_devices: set[str] = set()

    @override
    async def _async_setup(self) -> None:
        """Establish the first connection, before the initial refresh."""
        await self._async_connect()

    async def _async_connect(self) -> None:
        session = async_get_clientsession(self.hass)
        client = CoolbotClient(
            self.config_entry.data[CONF_EMAIL],
            self.config_entry.data[CONF_PASSWORD],
            session=session,
        )
        connected = False
        try:
            await client.async_connect()
            connected = True
        except CoolbotAuthError as err:
            # Prompts the user to re-enter credentials rather than retrying forever.
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except CoolbotError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            if not connected:
                # The socket and its reader task exist from partway through
                # connecting, and nothing else holds this client yet, so every
                # way of leaving without it — a rejected login, an unexpected
                # error, cancellation from a reload or shutdown — has to close
                # it here or it is leaked for the lifetime of the entry.
                await _async_close_client(client)

        self._client = client

    @override
    async def _async_update_data(self) -> dict[str, CoolbotDevice]:
        if self._client is None or not self._client.connected:
            _LOGGER.debug("Socket is down, reconnecting")
            await self._async_shutdown_client()
            await self._async_connect()

        assert self._client is not None
        try:
            # Never block a refresh waiting for a push; freshness is conveyed by
            # each device's data_age_seconds instead.
            devices = await self._client.async_get_devices(wait_for_live=False)
            await self._client.async_ping()
        except CoolbotAuthError as err:
            # Refreshes stop until reauth completes; the socket must not be
            # left open for that whole time.
            await self._async_shutdown_client()
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except CoolbotError as err:
            # Drop the socket so the next refresh reconnects from scratch.
            await self._async_shutdown_client()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(err)},
            ) from err

        # An empty list is a valid answer, not a failure: the profile is
        # authoritative, and treating it as an error would retain the previous
        # devices forever, leaving the last removed cooler undeletable and a
        # reload stuck retrying.
        # Devices already seen, by dashboard slot: the slot is stable across a
        # reconnect, while the unique id is not until the MAC has replayed.
        seen_by_slot = {device.target: device for device in (self.data or {}).values()}

        data: dict[str, CoolbotDevice] = {}
        for device in devices:
            if device.is_provisioned and not device.mac_address:
                # This device's MAC has not landed yet; it arrives as a replayed
                # pin. Its unique_id would be a dash/slot fallback that changes
                # once the MAC arrives, duplicating the device, so it cannot be
                # published under that id.
                if (already_seen := seen_by_slot.get(device.target)) is not None:
                    # Reconnecting only waits for the first replayed pin, which
                    # need not be this device's MAC. Carrying the last snapshot
                    # over the gap avoids reporting an outage that is not
                    # happening and flapping its entities for a cycle.
                    data[already_seen.unique_id] = already_seen
                    continue
                _LOGGER.debug(
                    "Holding back %s until its MAC address arrives", device.name
                )
                continue
            data[device.unique_id] = device

        self._log_staleness_transitions(data)
        return data

    def _log_staleness_transitions(self, data: dict[str, CoolbotDevice]) -> None:
        """Log once when a device stops reporting, and once when it recovers.

        A device that has not reported yet is not an outage: the cloud replays a
        cached snapshot on connect, so every device looks stale for the first few
        seconds of a normal setup. Only a device that was reporting can stop,
        whether it went stale or dropped out of the account's profile entirely.
        """
        for device in data.values():
            if not device.is_provisioned:
                continue
            fresh = device_is_fresh(device)
            known = self._reporting.get(device.unique_id)
            if known is None:
                if fresh:
                    self._reporting[device.unique_id] = (device.name, True)
                continue
            if fresh is known[1]:
                continue
            self._reporting[device.unique_id] = (device.name, fresh)
            self._log_transition(device.name, reporting=fresh)

        # A device missing from a successful refresh has also stopped
        # reporting: its entities go unavailable for want of any data, and
        # nothing above sees it, because it is no longer in the mapping.
        for unique_id, (name, was_fresh) in list(self._reporting.items()):
            if was_fresh and unique_id not in data:
                self._reporting[unique_id] = (name, False)
                self._log_transition(name, reporting=False)

    def _log_transition(self, name: str, *, reporting: bool) -> None:
        """Log one device's change of reporting state."""
        if reporting:
            _LOGGER.info("%s is reporting again", name)
        else:
            _LOGGER.info(
                "%s has stopped reporting; its readings are marked unavailable", name
            )

    def forget_device(self, unique_id: str) -> None:
        """Forget a device that Home Assistant has removed.

        Its entities go with it, so the same cooler returning to the account
        has to have them created again rather than being filtered out as one
        that already has them.
        """
        self.known_devices.discard(unique_id)
        self._reporting.pop(unique_id, None)

    @override
    async def async_shutdown(self) -> None:
        """Stop refreshing and close the socket."""
        await super().async_shutdown()
        await self._async_shutdown_client()

    async def _async_shutdown_client(self) -> None:
        if self._client is not None:
            client, self._client = self._client, None
            await _async_close_client(client)


async def _async_close_client(client: CoolbotClient) -> None:
    """Close a client without letting a failed close mask the real problem."""
    try:
        await client.async_close()
    except Exception:
        _LOGGER.debug("Error while closing the socket", exc_info=True)


def device_is_fresh(device: CoolbotDevice) -> bool:
    """Whether a device's readings should be trusted right now.

    A CoolBot that loses WiFi leaves the cloud serving its last known values, so
    a stale reading looks current. Entities go unavailable rather than reporting
    a temperature that has stopped moving.
    """
    if not device.is_provisioned:
        return False
    age = device.data_age_seconds
    if age is None:
        # The server replays a cached snapshot on connect that can be minutes
        # old, so nothing is trustworthy until a live push arrives this session.
        return False
    return age <= STALE_AFTER_SECONDS
