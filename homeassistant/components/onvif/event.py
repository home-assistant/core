"""ONVIF event abstraction."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import datetime as dt

from aiohttp.web import Request
from httpx import RemoteProtocolError, RequestError, TransportError
from onvif import ONVIFCamera, ONVIFService
from onvif.client import NotificationManager
from onvif.exceptions import ONVIFError
from zeep.exceptions import Fault, XMLParseError

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DOMAIN, LOGGER
from .models import Event, PullPointManagerState, WebHookManagerState
from .parsers import PARSERS
from .util import stringify_onvif_error

# Topics in this list are ignored because we do not want to create
# entities for them.
UNHANDLED_TOPICS: set[str] = {"tns1:MediaControl/VideoEncoderConfiguration"}

SUBSCRIPTION_ERRORS = (Fault, asyncio.TimeoutError, TransportError)
CREATE_ERRORS = (ONVIFError, Fault, RequestError, XMLParseError)
SET_SYNCHRONIZATION_POINT_ERRORS = (*SUBSCRIPTION_ERRORS, TypeError)
UNSUBSCRIBE_ERRORS = (XMLParseError, *SUBSCRIPTION_ERRORS)
RENEW_ERRORS = (ONVIFError, RequestError, XMLParseError, *SUBSCRIPTION_ERRORS)
#
# We only keep the subscription alive for 3 minutes, and will keep
# renewing it every 1.5 minutes. This is to avoid the camera
# accumulating subscriptions which will be impossible to clean up
# since ONVIF does not provide a way to list existing subscriptions.
#
# If we max out the number of subscriptions, the camera will stop
# sending events to us, and we will not be able to recover until
# the subscriptions expire or the camera is rebooted.
#
SUBSCRIPTION_TIME = dt.timedelta(minutes=3)
SUBSCRIPTION_RELATIVE_TIME = (
    "PT3M"  # use relative time since the time on the camera is not reliable
)
SUBSCRIPTION_RENEW_INTERVAL = SUBSCRIPTION_TIME.total_seconds() / 2
SUBSCRIPTION_RENEW_INTERVAL_ON_ERROR = 60.0

PULLPOINT_POLL_TIME = dt.timedelta(seconds=60)
PULLPOINT_MESSAGE_LIMIT = 100
PULLPOINT_COOLDOWN_TIME = 0.75


class EventManager:
    """ONVIF Event Manager."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: ONVIFCamera,
        config_entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize event manager."""
        self.hass = hass
        self.device = device
        self.config_entry = config_entry
        self.unique_id = config_entry.unique_id
        self.name = name

        self.webhook_manager = WebHookManager(self)
        self.pullpoint_manager = PullPointManager(self)

        self._uid_by_platform: dict[str, set[str]] = {}
        self._events: dict[str, Event] = {}
        self._listeners: list[CALLBACK_TYPE] = []

    @property
    def started(self) -> bool:
        """Return True if event manager is started."""
        return (
            self.webhook_manager.state == WebHookManagerState.STARTED
            or self.pullpoint_manager.state == PullPointManagerState.STARTED
        )

    @property
    def has_listeners(self) -> bool:
        """Return if there are listeners."""
        return bool(self._listeners)

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Listen for data updates."""
        # This is the first listener, set up polling.
        if not self._listeners:
            self.pullpoint_manager.async_schedule_pull_messages()

        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self.async_remove_listener(update_callback)

        return remove_listener

    @callback
    def async_remove_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Remove data update."""
        if update_callback in self._listeners:
            self._listeners.remove(update_callback)

        if not self._listeners:
            self.pullpoint_manager.async_cancel_pull_messages()

    async def async_start(self) -> bool:
        """Start polling events."""
        # Always start pull point first, since it will populate the event list
        event_via_pull_point = await self.pullpoint_manager.async_start()
        events_via_webhook = await self.webhook_manager.async_start()
        return events_via_webhook or event_via_pull_point

    async def async_stop(self) -> None:
        """Unsubscribe from events."""
        self._listeners = []
        await self.pullpoint_manager.async_stop()
        await self.webhook_manager.async_stop()

    @callback
    def async_callback_listeners(self) -> None:
        """Update listeners."""
        for update_callback in self._listeners:
            update_callback()

    # pylint: disable=protected-access
    async def async_parse_messages(self, messages) -> None:
        """Parse notification message."""
        unique_id = self.unique_id
        assert unique_id is not None
        for msg in messages:
            # Guard against empty message
            if not msg.Topic:
                continue

            # Topic may look like the following
            #
            # tns1:RuleEngine/CellMotionDetector/Motion//.
            # tns1:RuleEngine/CellMotionDetector/Motion
            # tns1:RuleEngine/CellMotionDetector/Motion/
            #
            # Our parser expects the topic to be
            # tns1:RuleEngine/CellMotionDetector/Motion
            topic = msg.Topic._value_1.rstrip("/.")

            if not (parser := PARSERS.get(topic)):
                if topic not in UNHANDLED_TOPICS:
                    LOGGER.info(
                        "%s: No registered handler for event from %s: %s",
                        self.name,
                        unique_id,
                        msg,
                    )
                    UNHANDLED_TOPICS.add(topic)
                continue

            event = await parser(unique_id, msg)

            if not event:
                LOGGER.info(
                    "%s: Unable to parse event from %s: %s", self.name, unique_id, msg
                )
                return

            self.get_uids_by_platform(event.platform).add(event.uid)
            self._events[event.uid] = event

    def get_uid(self, uid: str) -> Event | None:
        """Retrieve event for given id."""
        return self._events.get(uid)

    def get_platform(self, platform) -> list[Event]:
        """Retrieve events for given platform."""
        return [event for event in self._events.values() if event.platform == platform]

    def get_uids_by_platform(self, platform: str) -> set[str]:
        """Retrieve uids for a given platform."""
        if (possible_uids := self._uid_by_platform.get(platform)) is None:
            uids: set[str] = set()
            self._uid_by_platform[platform] = uids
            return uids
        return possible_uids

    @callback
    def async_webhook_failed(self) -> None:
        """Mark webhook as failed."""
        if self.pullpoint_manager.state != PullPointManagerState.PAUSED:
            return
        LOGGER.debug("%s: Switching to PullPoint for events", self.name)
        self.pullpoint_manager.async_resume()

    @callback
    def async_webhook_working(self) -> None:
        """Mark webhook as working."""
        if self.pullpoint_manager.state != PullPointManagerState.STARTED:
            return
        LOGGER.debug("%s: Switching to webhook for events", self.name)
        self.pullpoint_manager.async_pause()

    @callback
    def async_mark_events_stale(self) -> None:
        """Mark all events as stale when the subscriptions fail since we are out of sync."""
        self._events.clear()
        self.async_callback_listeners()


class PullPointManager:
    """ONVIF PullPoint Manager.

    If the camera supports webhooks and the webhook is reachable, the pullpoint
    manager will keep the pull point subscription alive, but will not poll for
    messages unless the webhook fails.
    """

    def __init__(self, event_manager: EventManager) -> None:
        """Initialize pullpoint manager."""
        self.state = PullPointManagerState.STOPPED

        self._event_manager = event_manager
        self._device = event_manager.device
        self._hass = event_manager.hass
        self._name = event_manager.name

        self._pullpoint_subscription: ONVIFService = None
        self._pullpoint_service: ONVIFService = None
        self._pull_lock: asyncio.Lock = asyncio.Lock()

        self._cancel_pull_messages: CALLBACK_TYPE | None = None
        self._cancel_pullpoint_renew: CALLBACK_TYPE | None = None

        self._renew_lock: asyncio.Lock = asyncio.Lock()
        self._renew_or_restart_job = HassJob(
            self._async_renew_or_restart_pullpoint,
            f"{self._name}: renew or restart pullpoint",
        )
        self._pull_messages_job = HassJob(
            self._async_background_pull_messages,
            f"{self._name}: pull messages",
        )

    async def async_start(self) -> bool:
        """Start pullpoint subscription."""
        assert (
            self.state == PullPointManagerState.STOPPED
        ), "PullPoint manager already started"
        LOGGER.debug("%s: Starting PullPoint manager", self._name)
        if not await self._async_start_pullpoint():
            self.state = PullPointManagerState.FAILED
            return False
        self.state = PullPointManagerState.STARTED
        return True

    @callback
    def async_pause(self) -> None:
        """Pause pullpoint subscription."""
        LOGGER.debug("%s: Pausing PullPoint manager", self._name)
        self.state = PullPointManagerState.PAUSED
        self._hass.async_create_task(self._async_cancel_and_unsubscribe())

    @callback
    def async_resume(self) -> None:
        """Resume pullpoint subscription."""
        LOGGER.debug("%s: Resuming PullPoint manager", self._name)
        self.state = PullPointManagerState.STARTED
        self.async_schedule_pullpoint_renew(0.0)

    @callback
    def async_schedule_pullpoint_renew(self, delay: float) -> None:
        """Schedule PullPoint subscription renewal."""
        self._async_cancel_pullpoint_renew()
        self._cancel_pullpoint_renew = async_call_later(
            self._hass,
            delay,
            self._renew_or_restart_job,
        )

    @callback
    def async_cancel_pull_messages(self) -> None:
        """Cancel the PullPoint task."""
        if self._cancel_pull_messages:
            self._cancel_pull_messages()
            self._cancel_pull_messages = None

    @callback
    def async_schedule_pull_messages(self, delay: float | None = None) -> None:
        """Schedule async_pull_messages to run.

        Used as fallback when webhook is not working.

        Must not check if the webhook is working.
        """
        self.async_cancel_pull_messages()
        if self.state != PullPointManagerState.STARTED:
            return
        if self._pullpoint_service:
            when = delay if delay is not None else PULLPOINT_COOLDOWN_TIME
            self._cancel_pull_messages = async_call_later(
                self._hass, when, self._pull_messages_job
            )

    async def async_stop(self) -> None:
        """Unsubscribe from PullPoint and cancel callbacks."""
        self.state = PullPointManagerState.STOPPED
        await self._async_cancel_and_unsubscribe()

    async def _async_start_pullpoint(self) -> bool:
        """Start pullpoint subscription."""
        try:
            try:
                started = await self._async_create_pullpoint_subscription()
            except RequestError:
                #
                # We should only need to retry on RemoteProtocolError but some cameras
                # are flaky and sometimes do not respond to the Renew request so we
                # retry on RequestError as well.
                #
                # For RemoteProtocolError:
                # http://datatracker.ietf.org/doc/html/rfc2616#section-8.1.4 allows the server
                # to close the connection at any time, we treat this as a normal and try again
                # once since we do not want to declare the camera as not supporting PullPoint
                # if it just happened to close the connection at the wrong time.
                started = await self._async_create_pullpoint_subscription()
        except CREATE_ERRORS as err:
            LOGGER.debug(
                "%s: Device does not support PullPoint service or has too many subscriptions: %s",
                self._name,
                stringify_onvif_error(err),
            )
            return False

        if started:
            self.async_schedule_pullpoint_renew(SUBSCRIPTION_RENEW_INTERVAL)

        return started

    async def _async_cancel_and_unsubscribe(self) -> None:
        """Cancel and unsubscribe from PullPoint."""
        self._async_cancel_pullpoint_renew()
        self.async_cancel_pull_messages()
        await self._async_unsubscribe_pullpoint()

    async def _async_renew_or_restart_pullpoint(
        self, now: dt.datetime | None = None
    ) -> None:
        """Renew or start pullpoint subscription."""
        if self._hass.is_stopping or self.state != PullPointManagerState.STARTED:
            return
        if self._renew_lock.locked():
            LOGGER.debug("%s: PullPoint renew already in progress", self._name)
            # Renew is already running, another one will be
            # scheduled when the current one is done if needed.
            return
        async with self._renew_lock:
            next_attempt = SUBSCRIPTION_RENEW_INTERVAL_ON_ERROR
            try:
                if (
                    await self._async_renew_pullpoint()
                    or await self._async_restart_pullpoint()
                ):
                    next_attempt = SUBSCRIPTION_RENEW_INTERVAL
            finally:
                self.async_schedule_pullpoint_renew(next_attempt)

    async def _async_create_pullpoint_subscription(self) -> bool:
        """Create pullpoint subscription."""

        if not await self._device.create_pullpoint_subscription(
            {"InitialTerminationTime": SUBSCRIPTION_RELATIVE_TIME}
        ):
            LOGGER.debug("%s: Failed to create PullPoint subscription", self._name)
            return False

        # Create subscription manager
        self._pullpoint_subscription = self._device.create_subscription_service(
            "PullPointSubscription"
        )

        # Create the service that will be used to pull messages from the device.
        self._pullpoint_service = self._device.create_pullpoint_service()

        # Initialize events
        with suppress(*SET_SYNCHRONIZATION_POINT_ERRORS):
            sync_result = await self._pullpoint_service.SetSynchronizationPoint()
            LOGGER.debug("%s: SetSynchronizationPoint: %s", self._name, sync_result)

        # Always schedule an initial pull messages
        self.async_schedule_pull_messages(0.0)

        return True

    @callback
    def _async_cancel_pullpoint_renew(self) -> None:
        """Cancel the pullpoint renew task."""
        if self._cancel_pullpoint_renew:
            self._cancel_pullpoint_renew()
            self._cancel_pullpoint_renew = None

    async def _async_restart_pullpoint(self) -> bool:
        """Restart the subscription assuming the camera rebooted."""
        self.async_cancel_pull_messages()
        await self._async_unsubscribe_pullpoint()
        restarted = await self._async_start_pullpoint()
        if restarted and self._event_manager.has_listeners:
            LOGGER.debug("%s: Restarted PullPoint subscription", self._name)
            self.async_schedule_pull_messages(0.0)
        return restarted

    async def _async_unsubscribe_pullpoint(self) -> None:
        """Unsubscribe the pullpoint subscription."""
        if (
            not self._pullpoint_subscription
            or self._pullpoint_subscription.transport.client.is_closed
        ):
            return
        LOGGER.debug("%s: Unsubscribing from PullPoint", self._name)
        try:
            await self._pullpoint_subscription.Unsubscribe()
        except UNSUBSCRIBE_ERRORS as err:
            LOGGER.debug(
                (
                    "%s: Failed to unsubscribe PullPoint subscription;"
                    " This is normal if the device restarted: %s"
                ),
                self._name,
                stringify_onvif_error(err),
            )
        self._pullpoint_subscription = None

    async def _async_renew_pullpoint(self) -> bool:
        """Renew the PullPoint subscription."""
        if (
            not self._pullpoint_subscription
            or self._pullpoint_subscription.transport.client.is_closed
        ):
            return False
        try:
            # The first time we renew, we may get a Fault error so we
            # suppress it. The subscription will be restarted in
            # async_restart later.
            try:
                await self._pullpoint_subscription.Renew(SUBSCRIPTION_RELATIVE_TIME)
            except RequestError:
                #
                # We should only need to retry on RemoteProtocolError but some cameras
                # are flaky and sometimes do not respond to the Renew request so we
                # retry on RequestError as well.
                #
                # For RemoteProtocolError:
                # http://datatracker.ietf.org/doc/html/rfc2616#section-8.1.4 allows the server
                # to close the connection at any time, we treat this as a normal and try again
                # once since we do not want to mark events as stale
                # if it just happened to close the connection at the wrong time.
                await self._pullpoint_subscription.Renew(SUBSCRIPTION_RELATIVE_TIME)
            LOGGER.debug("%s: Renewed PullPoint subscription", self._name)
            return True
        except RENEW_ERRORS as err:
            self._event_manager.async_mark_events_stale()
            LOGGER.debug(
                "%s: Failed to renew PullPoint subscription; %s",
                self._name,
                stringify_onvif_error(err),
            )
        return False

    async def _async_pull_messages_with_lock(self) -> bool:
        """Pull messages from device while holding the lock.

        This function must not be called directly, it should only
        be called from _async_pull_messages.

        Returns True if the subscription is working.

        Returns False if the subscription is not working and should be restarted.
        """
        assert self._pull_lock.locked(), "Pull lock must be held"
        assert self._pullpoint_service is not None, "PullPoint service does not exist"
        event_manager = self._event_manager
        LOGGER.debug(
            "%s: Pulling PullPoint messages timeout=%s limit=%s",
            self._name,
            PULLPOINT_POLL_TIME,
            PULLPOINT_MESSAGE_LIMIT,
        )
        try:
            response = await self._pullpoint_service.PullMessages(
                {
                    "MessageLimit": PULLPOINT_MESSAGE_LIMIT,
                    "Timeout": PULLPOINT_POLL_TIME,
                }
            )
        except RemoteProtocolError as err:
            # Either a shutdown event or the camera closed the connection. Because
            # http://datatracker.ietf.org/doc/html/rfc2616#section-8.1.4 allows the server
            # to close the connection at any time, we treat this as a normal. Some
            # cameras may close the connection if there are no messages to pull.
            LOGGER.debug(
                "%s: PullPoint subscription encountered a remote protocol error "
                "(this is normal for some cameras): %s",
                self._name,
                stringify_onvif_error(err),
            )
            return True
        except (XMLParseError, *SUBSCRIPTION_ERRORS) as err:
            # Device may not support subscriptions so log at debug level
            # when we get an XMLParseError
            LOGGER.debug(
                "%s: Failed to fetch PullPoint subscription messages: %s",
                self._name,
                stringify_onvif_error(err),
            )
            # Treat errors as if the camera restarted. Assume that the pullpoint
            # subscription is no longer valid.
            return False

        if self.state != PullPointManagerState.STARTED:
            # If the webhook became started working during the long poll,
            # and we got paused, our data is stale and we should not process it.
            LOGGER.debug(
                "%s: PullPoint is paused (likely due to working webhook), skipping PullPoint messages",
                self._name,
            )
            return True

        # Parse response
        if (notification_message := response.NotificationMessage) and (
            number_of_events := len(notification_message)
        ):
            LOGGER.debug(
                "%s: continuous PullMessages: %s event(s)",
                self._name,
                number_of_events,
            )
            await event_manager.async_parse_messages(notification_message)
            event_manager.async_callback_listeners()
        else:
            LOGGER.debug("%s: continuous PullMessages: no events", self._name)

        return True

    @callback
    def _async_background_pull_messages(self, _now: dt.datetime | None = None) -> None:
        """Pull messages from device in the background."""
        self._cancel_pull_messages = None
        self._hass.async_create_background_task(
            self._async_pull_messages(),
            f"{self._name} background pull messages",
        )

    async def _async_pull_messages(self) -> None:
        """Pull messages from device."""
        event_manager = self._event_manager

        if self._pull_lock.locked():
            # Pull messages if the lock is not already locked
            # any pull will do, so we don't need to wait for the lock
            LOGGER.debug(
                "%s: PullPoint subscription is already locked, skipping pull",
                self._name,
            )
            return

        async with self._pull_lock:
            # Before we pop out of the lock we always need to schedule the next pull
            # or call async_schedule_pullpoint_renew if the pull fails so the pull
            # loop continues.
            try:
                if self._hass.state == CoreState.running:
                    if not await self._async_pull_messages_with_lock():
                        self.async_schedule_pullpoint_renew(0.0)
                        return
            finally:
                if event_manager.has_listeners:
                    self.async_schedule_pull_messages()


class WebHookManager:
    """Manage ONVIF webhook subscriptions.

    If the camera supports webhooks, we will use that instead of
    pullpoint subscriptions as soon as we detect that the camera
    can reach our webhook.
    """

    def __init__(self, event_manager: EventManager) -> None:
        """Initialize webhook manager."""
        self.state = WebHookManagerState.STOPPED

        self._event_manager = event_manager
        self._device = event_manager.device
        self._hass = event_manager.hass
        self._webhook_unique_id = f"{DOMAIN}_{event_manager.config_entry.entry_id}"
        self._name = event_manager.name

        self._webhook_url: str | None = None

        self._webhook_subscription: ONVIFService | None = None
        self._notification_manager: NotificationManager | None = None

        self._cancel_webhook_renew: CALLBACK_TYPE | None = None
        self._renew_lock = asyncio.Lock()
        self._renew_or_restart_job = HassJob(
            self._async_renew_or_restart_webhook,
            f"{self._name}: renew or restart webhook",
        )

    async def async_start(self) -> bool:
        """Start polling events."""
        LOGGER.debug("%s: Starting webhook manager", self._name)
        assert (
            self.state == WebHookManagerState.STOPPED
        ), "Webhook manager already started"
        assert self._webhook_url is None, "Webhook already registered"
        self._async_register_webhook()
        if not await self._async_start_webhook():
            self.state = WebHookManagerState.FAILED
            return False
        self.state = WebHookManagerState.STARTED
        return True

    async def async_stop(self) -> None:
        """Unsubscribe from events."""
        self.state = WebHookManagerState.STOPPED
        self._async_cancel_webhook_renew()
        await self._async_unsubscribe_webhook()
        self._async_unregister_webhook()

    @callback
    def _async_schedule_webhook_renew(self, delay: float) -> None:
        """Schedule webhook subscription renewal."""
        self._async_cancel_webhook_renew()
        self._cancel_webhook_renew = async_call_later(
            self._hass,
            delay,
            self._renew_or_restart_job,
        )

    async def _async_create_webhook_subscription(self) -> None:
        """Create webhook subscription."""
        LOGGER.debug("%s: Creating webhook subscription", self._name)
        self._notification_manager = self._device.create_notification_manager(
            {
                "InitialTerminationTime": SUBSCRIPTION_RELATIVE_TIME,
                "ConsumerReference": {"Address": self._webhook_url},
            }
        )
        self._webhook_subscription = await self._notification_manager.setup()
        await self._notification_manager.start()
        LOGGER.debug("%s: Webhook subscription created", self._name)

    async def _async_start_webhook(self) -> bool:
        """Start webhook."""
        try:
            try:
                await self._async_create_webhook_subscription()
            except RequestError:
                #
                # We should only need to retry on RemoteProtocolError but some cameras
                # are flaky and sometimes do not respond to the Renew request so we
                # retry on RequestError as well.
                #
                # For RemoteProtocolError:
                # http://datatracker.ietf.org/doc/html/rfc2616#section-8.1.4 allows the server
                # to close the connection at any time, we treat this as a normal and try again
                # once since we do not want to declare the camera as not supporting webhooks
                # if it just happened to close the connection at the wrong time.
                await self._async_create_webhook_subscription()
        except CREATE_ERRORS as err:
            self._event_manager.async_webhook_failed()
            LOGGER.debug(
                "%s: Device does not support notification service or too many subscriptions: %s",
                self._name,
                stringify_onvif_error(err),
            )
            return False

        self._async_schedule_webhook_renew(SUBSCRIPTION_RENEW_INTERVAL)
        return True

    async def _async_restart_webhook(self) -> bool:
        """Restart the webhook subscription assuming the camera rebooted."""
        await self._async_unsubscribe_webhook()
        return await self._async_start_webhook()

    async def _async_renew_webhook(self) -> bool:
        """Renew webhook subscription."""
        if (
            not self._webhook_subscription
            or self._webhook_subscription.transport.client.is_closed
        ):
            return False
        try:
            try:
                await self._webhook_subscription.Renew(SUBSCRIPTION_RELATIVE_TIME)
            except RequestError:
                #
                # We should only need to retry on RemoteProtocolError but some cameras
                # are flaky and sometimes do not respond to the Renew request so we
                # retry on RequestError as well.
                #
                # For RemoteProtocolError:
                # http://datatracker.ietf.org/doc/html/rfc2616#section-8.1.4 allows the server
                # to close the connection at any time, we treat this as a normal and try again
                # once since we do not want to mark events as stale
                # if it just happened to close the connection at the wrong time.
                await self._webhook_subscription.Renew(SUBSCRIPTION_RELATIVE_TIME)
            LOGGER.debug("%s: Renewed Webhook subscription", self._name)
            return True
        except RENEW_ERRORS as err:
            self._event_manager.async_mark_events_stale()
            LOGGER.debug(
                "%s: Failed to renew webhook subscription %s",
                self._name,
                stringify_onvif_error(err),
            )
        return False

    async def _async_renew_or_restart_webhook(
        self, now: dt.datetime | None = None
    ) -> None:
        """Renew or start webhook subscription."""
        if self._hass.is_stopping or self.state != WebHookManagerState.STARTED:
            return
        if self._renew_lock.locked():
            LOGGER.debug("%s: Webhook renew already in progress", self._name)
            # Renew is already running, another one will be
            # scheduled when the current one is done if needed.
            return
        async with self._renew_lock:
            next_attempt = SUBSCRIPTION_RENEW_INTERVAL_ON_ERROR
            try:
                if (
                    await self._async_renew_webhook()
                    or await self._async_restart_webhook()
                ):
                    next_attempt = SUBSCRIPTION_RENEW_INTERVAL
            finally:
                self._async_schedule_webhook_renew(next_attempt)

    @callback
    def _async_register_webhook(self) -> None:
        """Register the webhook for motion events."""
        LOGGER.debug("%s: Registering webhook: %s", self._name, self._webhook_unique_id)

        try:
            base_url = get_url(self._hass, prefer_external=False)
        except NoURLAvailableError:
            try:
                base_url = get_url(self._hass, prefer_external=True)
            except NoURLAvailableError:
                return

        webhook_id = self._webhook_unique_id
        webhook.async_register(
            self._hass, DOMAIN, webhook_id, webhook_id, self._async_handle_webhook
        )
        webhook_path = webhook.async_generate_path(webhook_id)
        self._webhook_url = f"{base_url}{webhook_path}"
        LOGGER.debug("%s: Registered webhook: %s", self._name, webhook_id)

    @callback
    def _async_unregister_webhook(self):
        """Unregister the webhook for motion events."""
        LOGGER.debug(
            "%s: Unregistering webhook %s", self._name, self._webhook_unique_id
        )
        webhook.async_unregister(self._hass, self._webhook_unique_id)
        self._webhook_url = None

    async def _async_handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: Request
    ) -> None:
        """Handle incoming webhook."""
        content: bytes | None = None
        try:
            content = await request.read()
        except ConnectionResetError as ex:
            LOGGER.error("Error reading webhook: %s", ex)
            return
        except asyncio.CancelledError as ex:
            LOGGER.error("Error reading webhook: %s", ex)
            raise
        finally:
            self._hass.async_create_background_task(
                self._async_process_webhook(hass, webhook_id, content),
                f"ONVIF event webhook for {self._name}",
            )

    async def _async_process_webhook(
        self, hass: HomeAssistant, webhook_id: str, content: bytes | None
    ) -> None:
        """Process incoming webhook data in the background."""
        event_manager = self._event_manager
        if content is None:
            # webhook is marked as not working as something
            # went wrong. We will mark it as working again
            # when we receive a valid notification.
            event_manager.async_webhook_failed()
            return
        if not self._notification_manager:
            LOGGER.debug(
                "%s: Received webhook before notification manager is setup", self._name
            )
            return
        if not (result := self._notification_manager.process(content)):
            LOGGER.debug("%s: Failed to process webhook %s", self._name, webhook_id)
            return
        LOGGER.debug(
            "%s: Processed webhook %s with %s event(s)",
            self._name,
            webhook_id,
            len(result.NotificationMessage),
        )
        event_manager.async_webhook_working()
        await event_manager.async_parse_messages(result.NotificationMessage)
        event_manager.async_callback_listeners()

    @callback
    def _async_cancel_webhook_renew(self) -> None:
        """Cancel the webhook renew task."""
        if self._cancel_webhook_renew:
            self._cancel_webhook_renew()
            self._cancel_webhook_renew = None

    async def _async_unsubscribe_webhook(self) -> None:
        """Unsubscribe from the webhook."""
        if (
            not self._webhook_subscription
            or self._webhook_subscription.transport.client.is_closed
        ):
            return
        LOGGER.debug("%s: Unsubscribing from webhook", self._name)
        try:
            await self._webhook_subscription.Unsubscribe()
        except UNSUBSCRIBE_ERRORS as err:
            LOGGER.debug(
                (
                    "%s: Failed to unsubscribe webhook subscription;"
                    " This is normal if the device restarted: %s"
                ),
                self._name,
                stringify_onvif_error(err),
            )
        self._webhook_subscription = None
