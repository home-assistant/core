"""Coordinator for LinknLink eMotion Ultra devices."""

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
    TARGET_SUBSCRIPTION_CONFIRM_TIMEOUT,
    TARGET_UPDATE_COOLDOWN,
)

type LinknLinkConfigEntry = ConfigEntry[LinknLinkCoordinator]


@dataclass(frozen=True, slots=True)
class LinknLinkData:
    """Data provided to LinknLink entities."""

    environment_state: UltraEnvironmentState | None = None
    target_state: UltraPositionSubscriptionState | None = None


def _update_failed(err: Exception) -> UpdateFailed:
    """Return a translated update failure for a device communication error."""
    return UpdateFailed(
        translation_domain=DOMAIN,
        translation_key="update_error",
        translation_placeholders={"error": str(err) or type(err).__name__},
    )


class LinknLinkCoordinator(DataUpdateCoordinator[LinknLinkData]):
    """Manage one eMotion Ultra device.

    The device state (environment, zone counts) is polled from the local API.
    The radar pushes the coordinates of detected people over UDP after the
    integration subscribes to them; this is the target subscription.
    """

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
        self.target_subscription: UltraPositionSubscription | None = None
        self.data = LinknLinkData()
        self._target_subscription_connected: bool | None = None
        self._cancel_target_notification: Callable[[], None] | None = None
        self._target_notification_pending = False

    @override
    async def _async_setup(self) -> None:
        """Authenticate and subscribe to radar target updates."""
        try:
            self.session = await self.client.connect(self.device)
            self.target_subscription = UltraPositionSubscription(
                self.client,
                self.session,
                callback=self._async_handle_target_update,
                status_callback=self._async_handle_target_subscription_status,
            )
            await self.target_subscription.start()
            await self.target_subscription.wait_confirmed(
                TARGET_SUBSCRIPTION_CONFIRM_TIMEOUT
            )
            target_state = self.target_subscription.state
            self.data = replace(self.data, target_state=target_state)
            self._target_subscription_connected = target_state.subscribed
        except (OSError, TimeoutError, UltraError, ValueError) as err:
            raise _update_failed(err) from err

    @override
    async def _async_update_data(self) -> LinknLinkData:
        """Fetch the environmental and zone count state."""
        try:
            environment_state = await self.client.get_environment_state(self.session)
        except (OSError, TimeoutError, UltraError, ValueError) as err:
            raise _update_failed(err) from err
        return replace(self.data, environment_state=environment_state)

    @callback
    def _async_handle_target_update(self, update: UltraPositionUpdate) -> None:
        """Coalesce radar target updates before notifying entities."""
        assert self.target_subscription is not None
        target_state = self.target_subscription.state
        if self._target_subscription_connected is False:
            LOGGER.info("Ultra radar target subscription is available")
        self._target_subscription_connected = True
        if self._cancel_target_notification is not None:
            self._target_notification_pending = True
            return
        self._async_set_target_state(target_state)
        self._async_schedule_target_notification()

    @callback
    def _async_set_target_state(self, state: UltraPositionSubscriptionState) -> None:
        """Update radar target data without resetting the polling timer."""
        self.data = replace(self.data, target_state=state)
        self.async_update_listeners()

    @callback
    def _async_schedule_target_notification(self) -> None:
        """Start the radar target notification cooldown."""
        self._cancel_target_notification = async_call_later(
            self.hass,
            TARGET_UPDATE_COOLDOWN,
            self._async_flush_target_notification,
        )

    @callback
    def _async_flush_target_notification(self, _: datetime) -> None:
        """Notify listeners of the latest radar targets after the cooldown."""
        self._cancel_target_notification = None
        if not self._target_notification_pending:
            return
        self._target_notification_pending = False
        if self.target_subscription is None:
            return
        self._async_set_target_state(self.target_subscription.state)
        self._async_schedule_target_notification()

    @callback
    def _async_cancel_target_notification(self) -> None:
        """Cancel a pending radar target notification."""
        if self._cancel_target_notification is not None:
            self._cancel_target_notification()
            self._cancel_target_notification = None
        self._target_notification_pending = False

    @callback
    def _async_handle_target_subscription_status(
        self, state: UltraPositionSubscriptionState
    ) -> None:
        """Update entities after meaningful subscription or expiry changes."""
        previous = self.data.target_state
        was_connected = self._target_subscription_connected
        initial_pending = (
            was_connected is None and not state.subscribed and state.last_error is None
        )
        if not initial_pending:
            self._target_subscription_connected = state.subscribed
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
                "Ultra radar target subscription is unavailable: %s",
                state.last_error,
            )
        elif state.subscribed and was_connected is False:
            LOGGER.info("Ultra radar target subscription is available")
        self._async_cancel_target_notification()
        self._async_set_target_state(state)

    @override
    async def async_shutdown(self) -> None:
        """Stop the radar target subscription and release its socket."""
        self._async_cancel_target_notification()
        if self.target_subscription is not None:
            await self.target_subscription.stop()
            self.target_subscription = None
        await super().async_shutdown()
