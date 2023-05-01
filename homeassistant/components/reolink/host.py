"""Module which encapsulates the NVR/camera API and subscription."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
from aiohttp.web import Request
import async_timeout
from reolink_aio.api import Host
from reolink_aio.exceptions import ReolinkError, SubscriptionError

from homeassistant.components import webhook
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CONF_PROTOCOL, CONF_USE_HTTPS, DOMAIN
from .exceptions import ReolinkSetupException, ReolinkWebhookException, UserNotAdmin

DEFAULT_TIMEOUT = 60
FIRST_ONVIF_TIMEOUT = 15
SUBSCRIPTION_RENEW_THRESHOLD = 300

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

        self.webhook_id: str | None = None
        self._base_url: str = ""
        self._webhook_url: str = ""
        self._webhook_reachable: asyncio.Event = asyncio.Event()
        self._lost_subscription: bool = False

    @property
    def unique_id(self) -> str:
        """Create the unique ID, base for all entities."""
        return self._unique_id

    @property
    def api(self):
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

        enable_rtsp = None
        enable_onvif = None
        enable_rtmp = None

        if not self._api.rtsp_enabled:
            _LOGGER.debug(
                "RTSP is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_rtsp = True

        if not self._api.onvif_enabled:
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

        await self.subscribe()

        _LOGGER.debug(
            "Waiting for initial ONVIF state on webhook '%s'", self._webhook_url
        )
        try:
            async with async_timeout.timeout(FIRST_ONVIF_TIMEOUT):
                await self._webhook_reachable.wait()
        except asyncio.TimeoutError:
            _LOGGER.debug(
                "Did not receive initial ONVIF state on webhook '%s' after %i seconds",
                self._webhook_url,
                FIRST_ONVIF_TIMEOUT,
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
        else:
            ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")

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

    async def update_states(self) -> None:
        """Call the API of the camera device to update the internal states."""
        await self._api.get_states()

    async def disconnect(self):
        """Disconnect from the API, so the connection will be released."""
        try:
            await self._api.unsubscribe()
        except (
            aiohttp.ClientConnectorError,
            asyncio.TimeoutError,
            ReolinkError,
        ) as err:
            _LOGGER.error(
                "Reolink error while unsubscribing from host %s:%s: %s",
                self._api.host,
                self._api.port,
                str(err),
            )

        try:
            await self._api.logout()
        except (
            aiohttp.ClientConnectorError,
            asyncio.TimeoutError,
            ReolinkError,
        ) as err:
            _LOGGER.error(
                "Reolink error while logging out for host %s:%s: %s",
                self._api.host,
                self._api.port,
                str(err),
            )

    async def stop(self, event=None):
        """Disconnect the API."""
        self.unregister_webhook()
        await self.disconnect()

    async def subscribe(self) -> None:
        """Subscribe to motion events and register the webhook as a callback."""
        if self.webhook_id is None:
            self.register_webhook()

        if self._api.subscribed:
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
            await self._renew()
        except SubscriptionError as err:
            if not self._lost_subscription:
                self._lost_subscription = True
                _LOGGER.error(
                    "Reolink %s event subscription lost: %s",
                    self._api.nvr_name,
                    str(err),
                )
        else:
            self._lost_subscription = False

    async def _renew(self) -> None:
        """Execute the renew of the subscription."""
        if not self._api.subscribed:
            _LOGGER.debug(
                "Host %s: requested to renew a non-existing Reolink subscription, "
                "trying to subscribe from scratch",
                self._api.host,
            )
            await self.subscribe()
            return

        timer = self._api.renewtimer
        _LOGGER.debug(
            "Host %s:%s should renew subscription in: %i seconds",
            self._api.host,
            self._api.port,
            timer,
        )
        if timer > SUBSCRIPTION_RENEW_THRESHOLD:
            return

        if timer > 0:
            try:
                await self._api.renew()
            except SubscriptionError as err:
                _LOGGER.debug(
                    "Host %s: error renewing Reolink subscription, "
                    "trying to subscribe again: %s",
                    self._api.host,
                    err,
                )
            else:
                _LOGGER.debug(
                    "Host %s successfully renewed Reolink subscription", self._api.host
                )
                return

        await self._api.subscribe(self._webhook_url)

        _LOGGER.debug(
            "Host %s: Reolink re-subscription successful after it was expired",
            self._api.host,
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

        _LOGGER.debug("Registered webhook: %s", event_id)

    def unregister_webhook(self):
        """Unregister the webhook for motion events."""
        _LOGGER.debug("Unregistering webhook %s", self.webhook_id)
        webhook.async_unregister(self._hass, self.webhook_id)
        self.webhook_id = None

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
        if not self._webhook_reachable.is_set():
            self._webhook_reachable.set()
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
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error processing ONVIF event for Reolink %s: %s",
                self._api.nvr_name,
                ex,
            )
            return

        if channels is None:
            async_dispatcher_send(hass, f"{webhook_id}_all", {})
            return

        for channel in channels:
            async_dispatcher_send(hass, f"{webhook_id}_{channel}", {})
