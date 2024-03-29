"""Module which encapsulates the NVR/camera API and subscription."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, Literal

import aiohttp
from aiohttp.web import Request
from reolink_aio.api import Host
from reolink_aio.enums import SubType
from reolink_aio.exceptions import NotSupportedError, ReolinkError, SubscriptionError

from homeassistant.components import webhook
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CONF_USE_HTTPS, DOMAIN
from .exceptions import ReolinkSetupException, ReolinkWebhookException, UserNotAdmin

DEFAULT_TIMEOUT = 30
FIRST_ONVIF_TIMEOUT = 10
FIRST_ONVIF_LONG_POLL_TIMEOUT = 90
SUBSCRIPTION_RENEW_THRESHOLD = 300
POLL_INTERVAL_NO_PUSH = 5
LONG_POLL_COOLDOWN = 0.75
LONG_POLL_ERROR_COOLDOWN = 30

_LOGGER = logging.getLogger(__name__)


class ReolinkHost:
    """The implementation of the Reolink Host class."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any],
        options: Mapping[str, Any],
    ) -> None:
        """Initialize Reolink Host. Could be either NVR, or Camera."""
        self._hass: HomeAssistant = hass

        self._clientsession: aiohttp.ClientSession | None = None
        self._unique_id: str = ""

        self._api = Host(
            config[CONF_HOST],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            port=config.get(CONF_PORT),
            use_https=config.get(CONF_USE_HTTPS),
            protocol=options[CONF_PROTOCOL],
            timeout=DEFAULT_TIMEOUT,
        )

        self.update_cmd_list: list[str] = []

        self.webhook_id: str | None = None
        self._onvif_push_supported: bool = True
        self._onvif_long_poll_supported: bool = True
        self._base_url: str = ""
        self._webhook_url: str = ""
        self._webhook_reachable: bool = False
        self._long_poll_received: bool = False
        self._long_poll_error: bool = False
        self._cancel_poll: CALLBACK_TYPE | None = None
        self._cancel_onvif_check: CALLBACK_TYPE | None = None
        self._cancel_long_poll_check: CALLBACK_TYPE | None = None
        self._poll_job = HassJob(self._async_poll_all_motion, cancel_on_shutdown=True)
        self._long_poll_task: asyncio.Task | None = None
        self._lost_subscription: bool = False

    @property
    def unique_id(self) -> str:
        """Create the unique ID, base for all entities."""
        return self._unique_id

    @property
    def api(self) -> Host:
        """Return the API object."""
        return self._api

    async def async_init(self) -> None:
        """Connect to Reolink host."""
        await self._api.get_host_data()

        if self._api.mac_address is None:
            raise ReolinkSetupException("Could not get mac address")

        if not self._api.is_admin:
            raise UserNotAdmin(
                f"User '{self._api.username}' has authorization level "
                f"'{self._api.user_level}', only admin users can change camera settings"
            )

        onvif_supported = self._api.supported(None, "ONVIF")
        self._onvif_push_supported = onvif_supported
        self._onvif_long_poll_supported = onvif_supported

        enable_rtsp = None
        enable_onvif = None
        enable_rtmp = None

        if not self._api.rtsp_enabled:
            _LOGGER.debug(
                "RTSP is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_rtsp = True

        if not self._api.onvif_enabled and onvif_supported:
            _LOGGER.debug(
                "ONVIF is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_onvif = True

        if not self._api.rtmp_enabled and self._api.protocol == "rtmp":
            _LOGGER.debug(
                "RTMP is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_rtmp = True

        if enable_onvif or enable_rtmp or enable_rtsp:
            try:
                await self._api.set_net_port(
                    enable_onvif=enable_onvif,
                    enable_rtmp=enable_rtmp,
                    enable_rtsp=enable_rtsp,
                )
            except ReolinkError:
                ports = ""
                if enable_rtsp:
                    ports += "RTSP "

                if enable_onvif:
                    ports += "ONVIF "

                if enable_rtmp:
                    ports += "RTMP "

                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    "enable_port",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="enable_port",
                    translation_placeholders={
                        "name": self._api.nvr_name,
                        "ports": ports,
                        "info_link": "https://support.reolink.com/hc/en-us/articles/900004435763-How-to-Set-up-Reolink-Ports-Settings-via-Reolink-Client-New-Client-",
                    },
                )
        else:
            ir.async_delete_issue(self._hass, DOMAIN, "enable_port")

        self._unique_id = format_mac(self._api.mac_address)

        if self._onvif_push_supported:
            try:
                await self.subscribe()
            except ReolinkError:
                self._onvif_push_supported = False
                self.unregister_webhook()
                await self._api.unsubscribe()
            else:
                if self._api.supported(None, "initial_ONVIF_state"):
                    _LOGGER.debug(
                        "Waiting for initial ONVIF state on webhook '%s'",
                        self._webhook_url,
                    )
                else:
                    _LOGGER.debug(
                        "Camera model %s most likely does not push its initial state"
                        " upon ONVIF subscription, do not check",
                        self._api.model,
                    )
                self._cancel_onvif_check = async_call_later(
                    self._hass, FIRST_ONVIF_TIMEOUT, self._async_check_onvif
                )
        if not self._onvif_push_supported:
            _LOGGER.debug(
                "Camera model %s does not support ONVIF push, using ONVIF long polling instead",
                self._api.model,
            )
            try:
                await self._async_start_long_polling(initial=True)
            except NotSupportedError:
                _LOGGER.debug(
                    "Camera model %s does not support ONVIF long polling, using fast polling instead",
                    self._api.model,
                )
                self._onvif_long_poll_supported = False
                await self._api.unsubscribe()
                await self._async_poll_all_motion()
            else:
                self._cancel_long_poll_check = async_call_later(
                    self._hass,
                    FIRST_ONVIF_LONG_POLL_TIMEOUT,
                    self._async_check_onvif_long_poll,
                )

        if self._api.sw_version_update_required:
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                "firmware_update",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="firmware_update",
                translation_placeholders={
                    "required_firmware": self._api.sw_version_required.version_string,
                    "current_firmware": self._api.sw_version,
                    "model": self._api.model,
                    "hw_version": self._api.hardware_version,
                    "name": self._api.nvr_name,
                    "download_link": "https://reolink.com/download-center/",
                },
            )
        else:
            ir.async_delete_issue(self._hass, DOMAIN, "firmware_update")

    async def _async_check_onvif(self, *_) -> None:
        """Check the ONVIF subscription."""
        if self._webhook_reachable:
            ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")
            self._cancel_onvif_check = None
            return
        if self._api.supported(None, "initial_ONVIF_state"):
            _LOGGER.debug(
                "Did not receive initial ONVIF state on webhook '%s' after %i seconds",
                self._webhook_url,
                FIRST_ONVIF_TIMEOUT,
            )

        # ONVIF push is not received, start long polling and schedule check
        await self._async_start_long_polling()
        self._cancel_long_poll_check = async_call_later(
            self._hass, FIRST_ONVIF_LONG_POLL_TIMEOUT, self._async_check_onvif_long_poll
        )

        self._cancel_onvif_check = None

    async def _async_check_onvif_long_poll(self, *_) -> None:
        """Check if ONVIF long polling is working."""
        if not self._long_poll_received:
            _LOGGER.debug(
                "Did not receive state through ONVIF long polling after %i seconds",
                FIRST_ONVIF_LONG_POLL_TIMEOUT,
            )
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                "webhook_url",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="webhook_url",
                translation_placeholders={
                    "name": self._api.nvr_name,
                    "base_url": self._base_url,
                    "network_link": "https://my.home-assistant.io/redirect/network/",
                },
            )

            if self._base_url.startswith("https"):
                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    "https_webhook",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="https_webhook",
                    translation_placeholders={
                        "base_url": self._base_url,
                        "network_link": "https://my.home-assistant.io/redirect/network/",
                    },
                )
            else:
                ir.async_delete_issue(self._hass, DOMAIN, "https_webhook")

            if self._hass.config.api is not None and self._hass.config.api.use_ssl:
                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    "ssl",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="ssl",
                    translation_placeholders={
                        "ssl_link": "https://www.home-assistant.io/integrations/http/#ssl_certificate",
                        "base_url": self._base_url,
                        "network_link": "https://my.home-assistant.io/redirect/network/",
                        "nginx_link": "https://github.com/home-assistant/addons/tree/master/nginx_proxy",
                    },
                )
            else:
                ir.async_delete_issue(self._hass, DOMAIN, "ssl")
        else:
            ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")
            ir.async_delete_issue(self._hass, DOMAIN, "https_webhook")
            ir.async_delete_issue(self._hass, DOMAIN, "ssl")

        # If no ONVIF push or long polling state is received, start fast polling
        await self._async_poll_all_motion()

        self._cancel_long_poll_check = None

    async def update_states(self) -> None:
        """Call the API of the camera device to update the internal states."""
        await self._api.get_states(cmd_list=self.update_cmd_list)

    async def disconnect(self) -> None:
        """Disconnect from the API, so the connection will be released."""
        try:
            await self._api.unsubscribe()
        except ReolinkError as err:
            _LOGGER.error(
                "Reolink error while unsubscribing from host %s:%s: %s",
                self._api.host,
                self._api.port,
                err,
            )

        try:
            await self._api.logout()
        except ReolinkError as err:
            _LOGGER.error(
                "Reolink error while logging out for host %s:%s: %s",
                self._api.host,
                self._api.port,
                err,
            )

    async def _async_start_long_polling(self, initial=False) -> None:
        """Start ONVIF long polling task."""
        if self._long_poll_task is None:
            try:
                await self._api.subscribe(sub_type=SubType.long_poll)
            except NotSupportedError as err:
                if initial:
                    raise
                # make sure the long_poll_task is always created to try again later
                if not self._lost_subscription:
                    self._lost_subscription = True
                    _LOGGER.error(
                        "Reolink %s event long polling subscription lost: %s",
                        self._api.nvr_name,
                        err,
                    )
            except ReolinkError as err:
                # make sure the long_poll_task is always created to try again later
                if not self._lost_subscription:
                    self._lost_subscription = True
                    _LOGGER.error(
                        "Reolink %s event long polling subscription lost: %s",
                        self._api.nvr_name,
                        err,
                    )
            else:
                self._lost_subscription = False
            self._long_poll_task = asyncio.create_task(self._async_long_polling())

    async def _async_stop_long_polling(self) -> None:
        """Stop ONVIF long polling task."""
        if self._long_poll_task is not None:
            self._long_poll_task.cancel()
            self._long_poll_task = None

        await self._api.unsubscribe(sub_type=SubType.long_poll)

    async def stop(self, event=None) -> None:
        """Disconnect the API."""
        if self._cancel_poll is not None:
            self._cancel_poll()
            self._cancel_poll = None
        if self._cancel_onvif_check is not None:
            self._cancel_onvif_check()
            self._cancel_onvif_check = None
        if self._cancel_long_poll_check is not None:
            self._cancel_long_poll_check()
            self._cancel_long_poll_check = None
        await self._async_stop_long_polling()
        self.unregister_webhook()
        await self.disconnect()

    async def subscribe(self) -> None:
        """Subscribe to motion events and register the webhook as a callback."""
        if self.webhook_id is None:
            self.register_webhook()

        if self._api.subscribed(SubType.push):
            _LOGGER.debug(
                "Host %s: is already subscribed to webhook %s",
                self._api.host,
                self._webhook_url,
            )
            return

        await self._api.subscribe(self._webhook_url)

        _LOGGER.debug(
            "Host %s: subscribed successfully to webhook %s",
            self._api.host,
            self._webhook_url,
        )

    async def renew(self) -> None:
        """Renew the subscription of motion events (lease time is 15 minutes)."""
        try:
            if self._onvif_push_supported:
                await self._renew(SubType.push)

            if self._onvif_long_poll_supported and self._long_poll_task is not None:
                if not self._api.subscribed(SubType.long_poll):
                    _LOGGER.debug("restarting long polling task")
                    # To prevent 5 minute request timeout
                    await self._async_stop_long_polling()
                    await self._async_start_long_polling()
                else:
                    await self._renew(SubType.long_poll)
        except SubscriptionError as err:
            if not self._lost_subscription:
                self._lost_subscription = True
                _LOGGER.error(
                    "Reolink %s event subscription lost: %s",
                    self._api.nvr_name,
                    err,
                )
        else:
            self._lost_subscription = False

    async def _renew(self, sub_type: Literal[SubType.push, SubType.long_poll]) -> None:
        """Execute the renew of the subscription."""
        if not self._api.subscribed(sub_type):
            _LOGGER.debug(
                "Host %s: requested to renew a non-existing Reolink %s subscription, "
                "trying to subscribe from scratch",
                self._api.host,
                sub_type,
            )
            if sub_type == SubType.push:
                await self.subscribe()
            else:
                await self._api.subscribe(self._webhook_url, sub_type)
            return

        timer = self._api.renewtimer(sub_type)
        _LOGGER.debug(
            "Host %s:%s should renew %s subscription in: %i seconds",
            self._api.host,
            self._api.port,
            sub_type,
            timer,
        )
        if timer > SUBSCRIPTION_RENEW_THRESHOLD:
            return

        if timer > 0:
            try:
                await self._api.renew(sub_type)
            except SubscriptionError as err:
                _LOGGER.debug(
                    "Host %s: error renewing Reolink %s subscription, "
                    "trying to subscribe again: %s",
                    self._api.host,
                    sub_type,
                    err,
                )
            else:
                _LOGGER.debug(
                    "Host %s successfully renewed Reolink %s subscription",
                    self._api.host,
                    sub_type,
                )
                return

        await self._api.subscribe(self._webhook_url, sub_type)

        _LOGGER.debug(
            "Host %s: Reolink %s re-subscription successful after it was expired",
            self._api.host,
            sub_type,
        )

    def register_webhook(self) -> None:
        """Register the webhook for motion events."""
        self.webhook_id = f"{DOMAIN}_{self.unique_id.replace(':', '')}_ONVIF"
        event_id = self.webhook_id

        webhook.async_register(
            self._hass, DOMAIN, event_id, event_id, self.handle_webhook
        )

        try:
            self._base_url = get_url(self._hass, prefer_external=False)
        except NoURLAvailableError:
            try:
                self._base_url = get_url(self._hass, prefer_external=True)
            except NoURLAvailableError as err:
                self.unregister_webhook()
                raise ReolinkWebhookException(
                    f"Error registering URL for webhook {event_id}: "
                    "HomeAssistant URL is not available"
                ) from err

        webhook_path = webhook.async_generate_path(event_id)
        self._webhook_url = f"{self._base_url}{webhook_path}"

        _LOGGER.debug("Registered webhook: %s", event_id)

    def unregister_webhook(self) -> None:
        """Unregister the webhook for motion events."""
        if self.webhook_id is None:
            return
        _LOGGER.debug("Unregistering webhook %s", self.webhook_id)
        webhook.async_unregister(self._hass, self.webhook_id)
        self.webhook_id = None

    async def _async_long_polling(self, *_) -> None:
        """Use ONVIF long polling to immediately receive events."""
        # This task will be cancelled once _async_stop_long_polling is called
        while True:
            if self._webhook_reachable:
                self._long_poll_task = None
                await self._async_stop_long_polling()
                return

            try:
                channels = await self._api.pull_point_request()
            except ReolinkError as ex:
                if not self._long_poll_error:
                    _LOGGER.error("Error while requesting ONVIF pull point: %s", ex)
                    await self._api.unsubscribe(sub_type=SubType.long_poll)
                self._long_poll_error = True
                await asyncio.sleep(LONG_POLL_ERROR_COOLDOWN)
                continue
            except Exception:
                _LOGGER.exception(
                    "Unexpected exception while requesting ONVIF pull point"
                )
                await self._api.unsubscribe(sub_type=SubType.long_poll)
                raise

            self._long_poll_error = False

            if not self._long_poll_received:
                self._long_poll_received = True
                ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")

            self._signal_write_ha_state(channels)

            # Cooldown to prevent CPU over usage on camera freezes
            await asyncio.sleep(LONG_POLL_COOLDOWN)

    async def _async_poll_all_motion(self, *_) -> None:
        """Poll motion and AI states until the first ONVIF push is received."""
        if self._webhook_reachable or self._long_poll_received:
            # ONVIF push or long polling is working, stop fast polling
            self._cancel_poll = None
            return

        try:
            await self._api.get_motion_state_all_ch()
        except ReolinkError as err:
            _LOGGER.error(
                "Reolink error while polling motion state for host %s:%s: %s",
                self._api.host,
                self._api.port,
                err,
            )
        finally:
            # schedule next poll
            if not self._hass.is_stopping:
                self._cancel_poll = async_call_later(
                    self._hass, POLL_INTERVAL_NO_PUSH, self._poll_job
                )

        self._signal_write_ha_state(None)

    async def handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: Request
    ) -> None:
        """Read the incoming webhook from Reolink for inbound messages and schedule processing."""
        _LOGGER.debug("Webhook '%s' called", webhook_id)
        data: bytes | None = None
        try:
            data = await request.read()
            if not data:
                _LOGGER.debug(
                    "Webhook '%s' triggered with unknown payload: %s", webhook_id, data
                )
        except ConnectionResetError:
            _LOGGER.debug(
                "Webhook '%s' called, but lost connection before reading message "
                "(ConnectionResetError), issuing poll",
                webhook_id,
            )
            return
        except aiohttp.ClientResponseError:
            _LOGGER.debug(
                "Webhook '%s' called, but could not read the message, issuing poll",
                webhook_id,
            )
            return
        except asyncio.CancelledError:
            _LOGGER.debug(
                "Webhook '%s' called, but lost connection before reading message "
                "(CancelledError), issuing poll",
                webhook_id,
            )
            raise
        finally:
            # We want handle_webhook to return as soon as possible
            # so we process the data in the background, this also shields from cancellation
            hass.async_create_background_task(
                self._process_webhook_data(hass, webhook_id, data),
                "Process Reolink webhook",
            )

    async def _process_webhook_data(
        self, hass: HomeAssistant, webhook_id: str, data: bytes | None
    ) -> None:
        """Process the data from the Reolink webhook."""
        # This task is executed in the background so we need to catch exceptions
        # and log them
        if not self._webhook_reachable:
            self._webhook_reachable = True
            ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")

        try:
            if not data:
                if not await self._api.get_motion_state_all_ch():
                    _LOGGER.error(
                        "Could not poll motion state after losing connection during receiving ONVIF event"
                    )
                    return
                async_dispatcher_send(hass, f"{webhook_id}_all", {})
                return

            message = data.decode("utf-8")
            channels = await self._api.ONVIF_event_callback(message)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error processing ONVIF event for Reolink %s", self._api.nvr_name
            )
            return

        self._signal_write_ha_state(channels)

    def _signal_write_ha_state(self, channels: list[int] | None) -> None:
        """Update the binary sensors with async_write_ha_state."""
        if channels is None:
            async_dispatcher_send(self._hass, f"{self.webhook_id}_all", {})
            return

        for channel in channels:
            async_dispatcher_send(self._hass, f"{self.webhook_id}_{channel}", {})

    @property
    def event_connection(self) -> str:
        """Type of connection to receive events."""
        if self._webhook_reachable:
            return "ONVIF push"
        if self._long_poll_received:
            return "ONVIF long polling"
        return "Fast polling"
