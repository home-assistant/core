"""DataUpdateCoordinator for a single ADAM Audio device.

Update loop
-----------
Every POLL_INTERVAL seconds the coordinator calls client.async_fetch_state(),
which sends a keepalive followed by GET commands for every controllable
parameter.  The GET responses populate client.state with the real device
values, so changes made via the physical knob or ADAM Audio's A
Control app are reflected in Home Assistant within one poll cycle.

If the fetch fails (device unreachable), UpdateFailed is raised so HA marks
all child entities as unavailable until the next successful poll.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AdamAudioClient, AdamAudioState
from .const import (
    CONF_DESCRIPTION,
    CONF_DEVICE_NAME,
    CONF_HOST,
    CONF_PORT,
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
            self.device_serial = self.client.serial

        # First refresh also does a full state poll so entities have real
        # values from the moment they appear in HA.
        await self.async_config_entry_first_refresh()

    async def async_shutdown(self) -> None:
        """Release resources when the config entry is unloaded."""
        await self.client.async_shutdown()

    # ── Coordinator update callback ───────────────────────────────────────────

    async def _async_update_data(self) -> AdamAudioState:
        """Fetch current device state.

        Sends keepalive + all GET commands.  On success, client.state holds
        the values the device reported; entities read from there.
        Raises UpdateFailed to mark entities unavailable if unreachable.
        """
        success = await self.client.async_fetch_state()
        if not success:
            raise UpdateFailed(
                f"Device '{self.device_description}' unreachable at "
                f"{self.client.host}:{self.client.port}"
            )
        return self.client.state

    # ── Device info (shared by all child entities) ────────────────────────────

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_unique_id)},
            name=self.device_description,
            manufacturer=MANUFACTURER,
            model="A-Series",
            serial_number=self.device_serial or None,
            configuration_url=None,
        )
