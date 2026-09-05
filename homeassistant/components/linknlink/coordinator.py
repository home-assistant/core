"""Coordinator for LinknLink eMotion Ultra local position updates."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
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
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    ENVIRONMENT_UPDATE_INTERVAL,
    LOGGER,
    POSITION_SUBSCRIPTION_CONFIRM_TIMEOUT,
    POSITION_UPDATE_COOLDOWN,
)

type LinknLinkConfigEntry = ConfigEntry[LinknLinkCoordinator]


@dataclass(frozen=True, slots=True)
class LinknLinkData:
    """Data provided to LinknLink entities."""

    environment_state: UltraEnvironmentState | None = None
    environment_available: bool = False
    position_state: UltraPositionSubscriptionState | None = None


class LinknLinkCoordinator(DataUpdateCoordinator[LinknLinkData]):
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
        self.session: UltraSession
        self.position_subscription: UltraPositionSubscription | None = None
        self.data = LinknLinkData()
        self._position_connected: bool | None = None
        self._environment_connected: bool | None = None
        self._cancel_position_notification: Callable[[], None] | None = None
        self._position_notification_pending = False

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
            position_state = self.position_subscription.state
            self.data = replace(self.data, position_state=position_state)
            self._position_connected = position_state.subscribed
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
    async def _async_update_data(self) -> LinknLinkData:
        """Refresh lower-frequency environmental and count state."""
        try:
            environment_state = await self.client.get_environment_state(self.session)
        except (OSError, TimeoutError, UltraError) as err:
            if self._environment_connected is not False:
                LOGGER.info("Ultra environmental state is unavailable: %s", err)
            self._environment_connected = False
            return replace(self.data, environment_available=False)
        if self._environment_connected is False:
            LOGGER.info("Ultra environmental state is available")
        self._environment_connected = True
        return replace(
            self.data,
            environment_state=environment_state,
            environment_available=True,
        )

    @callback
    def _async_handle_position(self, update: UltraPositionUpdate) -> None:
        """Coalesce target-position updates before notifying entities."""
        assert self.position_subscription is not None
        position_state = self.position_subscription.state
        if self._position_connected is False:
            LOGGER.info("Ultra local position subscription is available")
        self._position_connected = True
        if self._cancel_position_notification is not None:
            self._position_notification_pending = True
            return
        self._async_set_position_state(position_state)
        self._async_schedule_position_notification()

    @callback
    def _async_set_position_state(self, state: UltraPositionSubscriptionState) -> None:
        """Update position data without resetting the environmental poll timer."""
        self.data = replace(self.data, position_state=state)
        self.async_update_listeners()

    @callback
    def _async_schedule_position_notification(self) -> None:
        """Start the position notification cooldown."""
        self._cancel_position_notification = async_call_later(
            self.hass,
            POSITION_UPDATE_COOLDOWN,
            self._async_flush_position_notification,
        )

    @callback
    def _async_flush_position_notification(self, _: datetime) -> None:
        """Notify listeners of the latest position after the cooldown."""
        self._cancel_position_notification = None
        if not self._position_notification_pending:
            return
        self._position_notification_pending = False
        if self.position_subscription is None:
            return
        self._async_set_position_state(self.position_subscription.state)
        self._async_schedule_position_notification()

    @callback
    def _async_cancel_position_notification(self) -> None:
        """Cancel a pending position notification."""
        if self._cancel_position_notification is not None:
            self._cancel_position_notification()
            self._cancel_position_notification = None
        self._position_notification_pending = False

    @callback
    def _async_handle_position_status(
        self, state: UltraPositionSubscriptionState
    ) -> None:
        """Update entities after meaningful subscription or expiry changes."""
        previous = self.data.position_state
        was_connected = self._position_connected
        initial_pending = (
            was_connected is None and not state.subscribed and state.last_error is None
        )
        if not initial_pending:
            self._position_connected = state.subscribed
        if (
            was_connected is state.subscribed
            and previous is not None
            and (
                previous.subscribed,
                previous.stale,
                previous.last_error,
            )
            == (state.subscribed, state.stale, state.last_error)
        ):
            return
        if not state.subscribed and was_connected is not False and state.last_error:
            LOGGER.info(
                "Ultra local position subscription is unavailable: %s",
                state.last_error,
            )
        elif state.subscribed and was_connected is False:
            LOGGER.info("Ultra local position subscription is available")
        self._async_cancel_position_notification()
        self._async_set_position_state(state)

    @override
    async def async_shutdown(self) -> None:
        """Stop the local position subscription and release its socket."""
        self._async_cancel_position_notification()
        if self.position_subscription is not None:
            await self.position_subscription.stop()
            self.position_subscription = None
        await super().async_shutdown()
