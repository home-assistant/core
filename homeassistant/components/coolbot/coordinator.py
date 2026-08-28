"""Keeps a live connection to the CoolBot cloud and publishes state to entities."""

from datetime import datetime
import logging
from typing import override

from pycoolbot import CoolbotAuthError, CoolbotClient, CoolbotDevice, CoolbotError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    PROFILE_REFRESH_INTERVAL,
    STALE_AFTER_SECONDS,
    UPDATE_INTERVAL,
)

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
        #: Name and hardware details last written to the device registry, per
        #: unique id, so an unchanged refresh does not touch the registry at all.
        self._device_details: dict[str, tuple[str, str, str | None, str | None]] = {}
        #: When the account profile was last read, connecting included.
        self._profile_read_at: datetime | None = None

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
                # Nothing else holds this client yet, and its socket is already
                # open, so every way of leaving without it has to close it here
                # — cancellation included.
                await _async_close_client(client)

        # Connecting reads the profile, so the clock starts here.
        self._profile_read_at = dt_util.utcnow()
        self._client = client

    @override
    async def _async_update_data(self) -> dict[str, CoolbotDevice]:
        if self._client is None or not self._client.connected:
            _LOGGER.debug("Socket is down, reconnecting")
            await self._async_shutdown_client()
            await self._async_connect()

        assert self._client is not None
        try:
            await self._async_reread_profile_if_due()
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
        data: dict[str, CoolbotDevice] = {}
        for device in devices:
            if device.is_provisioned and not device.mac_address:
                # This device cannot be named yet: its MAC has never replayed,
                # or the client dropped the cached one when a replay timed out,
                # because the slot may hold replacement hardware by then.
                # Its unique_id would be a dash/slot fallback that changes once
                # the MAC arrives, duplicating the device — and republishing
                # the slot's previous occupant instead would restore an
                # identity the client just refused to vouch for. Held back;
                # a device it displaced goes unavailable rather than being
                # carried as if it were still on the account.
                _LOGGER.debug(
                    "Holding back %s until its MAC address arrives", device.name
                )
                continue
            data[device.unique_id] = device

        self._log_staleness_transitions(data)
        self._apply_late_device_details(data)
        return data

    async def _async_reread_profile_if_due(self) -> None:
        """Re-read the account profile from time to time.

        The client reads it while connecting and then serves the device list
        from it, so without this a cooler added to or removed from the account
        would go unnoticed until the socket happened to reconnect.
        """
        assert self._client is not None
        now = dt_util.utcnow()
        if (
            self._profile_read_at is not None
            and now - self._profile_read_at < PROFILE_REFRESH_INTERVAL
        ):
            return
        await self._client.async_refresh_profile()
        self._profile_read_at = now

    def _apply_late_device_details(self, data: dict[str, CoolbotDevice]) -> None:
        """Record device details that change after a cooler is created.

        Connecting waits for the pins that identify a cooler, not for all of
        them, so it can be registered before its model and firmware arrive.
        Device info is only read when an entity is added, so without this those
        details would stay missing until the entry is reloaded. The name rides
        along so a cooler renamed in the account is renamed here too; a name
        the user chose in Home Assistant still wins over it.
        """
        registry: dr.DeviceRegistry | None = None
        for unique_id, device in data.items():
            details = (
                device.name,
                device_model(device),
                device.jumper_firmware,
                device.jumper_hardware,
            )
            if self._device_details.get(unique_id) == details:
                continue
            if registry is None:
                registry = dr.async_get(self.hass)
            entry = registry.async_get_device_by_identifier(
                (DOMAIN, unique_id), self.config_entry.entry_id
            )
            if entry is None:
                # Its entities have not been created yet, so it will be
                # registered with whatever has replayed by then.
                continue
            self._device_details[unique_id] = details
            current = (entry.name, entry.model, entry.sw_version, entry.hw_version)
            if current == details:
                continue
            registry.async_update_device(
                entry.id,
                name=details[0],
                model=details[1],
                sw_version=details[2],
                hw_version=details[3],
            )

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
        self._device_details.pop(unique_id, None)

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


def device_model(device: CoolbotDevice) -> str:
    """Return the model name, including the hardware revision once known."""
    if device.coolbot_hardware:
        return f"CoolBot Pro {device.coolbot_hardware}"
    return "CoolBot Pro"


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
