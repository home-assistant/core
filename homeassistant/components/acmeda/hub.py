"""Code to handle a Pulse Hub."""

from collections.abc import Callable

import aiopulse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import ACMEDA_HUB_UPDATE, LOGGER
from .helpers import update_devices


class PulseHub:
    """Manages a single Pulse Hub."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.api: aiopulse.Hub | None = None
        self.cleanup_callbacks: list[Callable[[], None]] = []

    @property
    def title(self) -> str:
        """Return the title of the hub shown in the integrations list."""

        if self.api is None:
            return self.config_entry.data["host"]  # type: ignore[no-any-return]
        return f"{self.api.id} ({self.api.host})"

    @property
    def host(self) -> str:
        """Return the host of this hub."""
        return self.config_entry.data["host"]  # type: ignore[no-any-return]

    async def async_setup(self, tries: int = 0) -> bool:
        """Set up a hub based on host parameter."""
        self.api = hub = aiopulse.Hub(self.host)

        hub.callback_subscribe(self._schedule_update)

        LOGGER.debug("Hub setup complete")
        return True

    async def async_start(self) -> None:
        """Start the hub task."""
        LOGGER.debug("Hub task started")

        if self.api is None:
            return

        await self.api.run()

    async def async_reset(self) -> bool:
        """Reset this hub to default state."""
        LOGGER.debug("Resetting hub %s", self.title)

        for cleanup_callback in self.cleanup_callbacks:
            cleanup_callback()

        if self.api is None:
            return False

        self.api.callback_unsubscribe(self._schedule_update)
        await self.api.stop()
        del self.api
        self.api = None

        return True

    def _schedule_update(self, update_type: aiopulse.UpdateType) -> None:
        """Schedule update callback on the event loop from aiopulse thread."""
        self.hass.loop.call_soon_threadsafe(self._handle_update, update_type)

    @callback
    def _handle_update(self, update_type: aiopulse.UpdateType) -> None:
        """Handle hub update in the event loop."""
        self.hass.async_create_task(
            self.async_notify_update(update_type),
            f"acmeda hub update {update_type.name}",
        )

    async def async_notify_update(self, update_type: aiopulse.UpdateType) -> None:
        """Evaluate entities when hub reports that update has occurred."""
        LOGGER.debug("Hub %s updated", update_type.name)

        if self.api is None:
            return

        if update_type is aiopulse.UpdateType.rollers:
            LOGGER.debug(
                "Hub %s rollers updated, updating devices %s",
                self.title,
                self.api.rollers,
            )
            await update_devices(self.hass, self.config_entry, self.api.rollers)
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=self.title
            )

            async_dispatcher_send(
                self.hass, ACMEDA_HUB_UPDATE.format(self.config_entry.entry_id)
            )
