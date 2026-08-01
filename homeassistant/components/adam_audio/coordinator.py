"""DataUpdateCoordinator for a single ADAM Audio device.

Update loop
-----------
Every POLL_INTERVAL seconds the coordinator calls client.async_fetch_state(),
which sends a keepalive followed by GET commands for every controllable
parameter.  The GET responses populate client.state with the real device
values, so changes made via the physical knob or ADAM Audio's A
Control app are reflected in Home Assistant within one poll cycle.

If the fetch fails and the client's consecutive-failure streak reaches
AdamAudioClient.UNAVAILABLE_AFTER_FAILURES (client.available flips to
False), UpdateFailed is raised so HA marks all child entities as
unavailable until the next successful poll. A single dropped poll on its
own is tolerated and does not affect entity availability.
"""

from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING, override

from homeassistant.const import CONF_DESCRIPTION, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AdamAudioClient, AdamAudioState
from .const import (
    CONF_DEVICE_NAME,
    CONF_SERIAL,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    POLL_INTERVAL,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import AdamAudioConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class AdamAudioCoordinator(DataUpdateCoordinator[AdamAudioState]):
    """Manages one ADAM Audio device.

    One coordinator is created per config entry (= per physical speaker).
    The update loop runs every POLL_INTERVAL seconds and issues a full state
    poll (keepalive + all GET commands) to keep HA in sync with the device.
    """

    config_entry: AdamAudioConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AdamAudioConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = AdamAudioClient(
            hass,
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
        )

        # Metadata — may be refreshed from the live device during async_setup
        self.device_unique_id: str = entry.data[CONF_DEVICE_NAME]
        self.device_description: str = entry.data.get(CONF_DESCRIPTION, "ADAM Audio")
        self.device_serial: str = entry.data.get(CONF_SERIAL, "")

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{self.device_unique_id}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
            always_update=False,
            config_entry=entry,
        )

    # ── Public setup / teardown ───────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Connect to the device.

        Raises ConfigEntryNotReady if the device cannot be reached so HA
        retries later.
        """
        connected = await self.client.async_setup()
        if not connected:
            raise ConfigEntryNotReady(
                f"Cannot connect to ADAM Audio device at "
                f"{self.client.host}:{self.client.port}. "
                "Is the speaker powered on and on the local network?"
            )
        # Prefer live values over what was persisted in the config entry.
        if self.client.description:
            self.device_description = self.client.description
        if self.client.serial:
            # If a serial was already stored for this entry, the live one
            # must match it: a stale/reassigned IP can otherwise point at a
            # different A-Series device, silently swapping the coordinator's
            # identity (and exposed controls) for the wrong speaker.
            if self.device_serial and self.client.serial != self.device_serial:
                raise ConfigEntryNotReady(
                    f"Device at {self.client.host}:{self.client.port} reports "
                    f"serial '{self.client.serial}', but this entry is "
                    f"configured for serial '{self.device_serial}'. The IP "
                    "address may now belong to a different ADAM Audio speaker."
                )
            self.device_serial = self.client.serial

        # First refresh also does a full state poll so entities have real
        # values from the moment they appear in HA.
        await self.async_config_entry_first_refresh()

    @override
    async def async_shutdown(self) -> None:
        """Release resources when the config entry is unloaded.

        Must cancel the base class's scheduled refresh timer first —
        otherwise a poll already queued via loop.call_at() can still fire
        after the socket below is closed, sending on a dead file
        descriptor (OSError: Bad file descriptor).
        """
        await super().async_shutdown()
        await self.client.async_shutdown()

    # ── Coordinator update callback ───────────────────────────────────────────

    @override
    async def _async_update_data(self) -> AdamAudioState:
        """Fetch current device state.

        Sends keepalive + all GET commands.  On success, client.state holds
        the values the device reported; entities read from there.
        Raises UpdateFailed to mark entities unavailable if unreachable.

        Availability is read from client.available rather than this poll's
        own result: the client debounces failures over several consecutive
        polls, so a single dropped poll (e.g. a device rebooting after being
        power-cycled) doesn't flip entities unavailable and back.

        Returns a snapshot copy of the client state: the client mutates its
        state object in place, so returning it directly would make the
        coordinator's always_update=False comparison always see "no change"
        and never notify listeners of polled changes (physical knob or
        A Control app adjustments).
        """
        await self.client.async_fetch_state()
        if not self.client.available:
            raise UpdateFailed(
                f"Device '{self.device_description}' unreachable at "
                f"{self.client.host}:{self.client.port}"
            )
        return replace(self.client.state)

    @callback
    def async_notify_state(self) -> None:
        """Push the client's current state to all entities immediately.

        Used after SET commands so every sibling entity (e.g. numbers whose
        availability depends on voicing) refreshes without waiting a poll.
        """
        self.async_set_updated_data(replace(self.client.state))

    # ── Device info (shared by all child entities) ────────────────────────────

    @property
    def entity_unique_id_base(self) -> str:
        """Return the value entities should use to build their unique_id.

        Prefers the device serial, which is globally unique, over the
        hardware name (``device_unique_id``), which is not guaranteed to be
        unique across speakers and is only kept around to look up
        registry entries created before the serial was known (see
        ``_async_migrate_device_identifiers``).
        """
        return self.device_serial or self.device_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the device registry.

        The serial number is the preferred identifier (stable even if the
        hardware name changes); existing registry entries created with the
        name-based identifier are migrated in async_setup_entry.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self.entity_unique_id_base)},
            name=self.device_description,
            manufacturer=MANUFACTURER,
            model="A-Series",
            serial_number=self.device_serial or None,
            configuration_url=None,
        )
