"""Coordinator for LinknLink eMotion Ultra local position updates."""

from collections.abc import Callable
from typing import override

from aiolinknlink import (
    UltraClient,
    UltraDevice,
    UltraEnvironmentState,
    UltraError,
    UltraPositionSubscription,
    UltraPositionSubscriptionState,
    UltraPositionUpdate,
    UltraSession,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    ENVIRONMENT_UPDATE_INTERVAL,
    LOGGER,
    POSITION_SUBSCRIPTION_CONFIRM_TIMEOUT,
)

type LinknLinkConfigEntry = ConfigEntry[LinknLinkCoordinator]
type PositionListener = Callable[[UltraPositionUpdate | None], None]


class LinknLinkCoordinator(DataUpdateCoordinator[None]):
    """Manage one Ultra DNA session and local position subscription."""

    config_entry: LinknLinkConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LinknLinkConfigEntry,
        client: UltraClient,
        device: UltraDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=f"LinknLink {device.id}",
            update_interval=ENVIRONMENT_UPDATE_INTERVAL,
        )
        self.client = client
        self.device = device
        self.session: UltraSession | None = None
        self.position_subscription: UltraPositionSubscription | None = None
        self.position_state: UltraPositionSubscriptionState | None = None
        self.environment_state: UltraEnvironmentState | None = None
        self.environment_available = False
        self._position_listeners: set[PositionListener] = set()

    @override
    async def _async_setup(self) -> None:
        """Authenticate and start the local UDP position subscription."""
        try:
            self.session = await self.client.connect(self.device)
            self.position_subscription = UltraPositionSubscription(
                self.client,
                self.session,
                callback=self._async_handle_position,
                status_callback=self._async_handle_position_status,
            )
            await self.position_subscription.start()
            await self.position_subscription.wait_confirmed(
                POSITION_SUBSCRIPTION_CONFIRM_TIMEOUT
            )
            self.position_state = self.position_subscription.state
        except (OSError, TimeoutError, UltraError, ValueError) as err:
            if self.position_subscription is not None:
                await self.position_subscription.stop()
                self.position_subscription = None
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err

    @override
    async def _async_update_data(self) -> None:
        """Refresh lower-frequency environmental and occupancy state."""
        if self.session is None:
            return
        try:
            self.environment_state = await self.client.get_environment_state(
                self.session
            )
        except (OSError, TimeoutError, UltraError) as err:
            if self.environment_available:
                LOGGER.warning("Ultra environmental state is unavailable: %s", err)
            else:
                LOGGER.debug("Unable to read Ultra environmental state: %s", err)
            self.environment_available = False
            return
        self.environment_available = True

    @callback
    def async_add_position_listener(
        self, listener: PositionListener
    ) -> Callable[[], None]:
        """Register a callback for position or position-status changes."""
        self._position_listeners.add(listener)

        @callback
        def _remove_listener() -> None:
            self._position_listeners.discard(listener)

        return _remove_listener

    @callback
    def _async_handle_position(self, update: UltraPositionUpdate) -> None:
        """Forward a new target-position update to position entities."""
        assert self.position_subscription is not None
        self.position_state = self.position_subscription.state
        for listener in self._position_listeners:
            listener(update)

    @callback
    def _async_handle_position_status(
        self, state: UltraPositionSubscriptionState
    ) -> None:
        """Forward meaningful subscription or expiry state changes."""
        previous = self.position_state
        self.position_state = state
        if previous is not None and (
            previous.subscribed,
            previous.stale,
            previous.last_error,
        ) == (state.subscribed, state.stale, state.last_error):
            return
        if state.last_error and (previous is None or previous.subscribed):
            LOGGER.warning(
                "Ultra local position subscription is unavailable: %s",
                state.last_error,
            )
        elif state.subscribed and previous is not None and not previous.subscribed:
            LOGGER.info("Ultra local position subscription is available")
        for listener in self._position_listeners:
            listener(None)

    @override
    async def async_shutdown(self) -> None:
        """Stop the local position subscription and release its socket."""
        if self.position_subscription is not None:
            await self.position_subscription.stop()
            self.position_subscription = None
        await super().async_shutdown()
