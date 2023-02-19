"""This component encapsulates the NVR/camera API and subscription."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
from aiohttp.web import Request
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
        self._webhook_url: str | None = None
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

        enable_onvif = None
        enable_rtmp = None
        enable_rtsp = None

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
        elif not self._api.rtsp_enabled and self._api.protocol == "rtsp":
            _LOGGER.debug(
                "RTSP is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_rtsp = True

        if enable_onvif or enable_rtmp or enable_rtsp:
            try:
                await self._api.set_net_port(
                    enable_onvif=enable_onvif,
                    enable_rtmp=enable_rtmp,
                    enable_rtsp=enable_rtsp,
                )
            except ReolinkError:
                if enable_onvif:
                    _LOGGER.error(
                        "Failed to enable ONVIF on %s. "
                        "Set it to ON to receive notifications",
                        self._api.nvr_name,
                    )

                if enable_rtmp:
                    _LOGGER.error(
                        "Failed to enable RTMP on %s. Set it to ON",
                        self._api.nvr_name,
                    )
                elif enable_rtsp:
                    _LOGGER.error(
                        "Failed to enable RTSP on %s. Set it to ON",
                        self._api.nvr_name,
                    )

        self._unique_id = format_mac(self._api.mac_address)

        await self.subscribe()

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
            base_url = get_url(self._hass, prefer_external=False)
        except NoURLAvailableError:
            try:
                base_url = get_url(self._hass, prefer_external=True)
            except NoURLAvailableError as err:
                self.unregister_webhook()
                raise ReolinkWebhookException(
                    f"Error registering URL for webhook {event_id}: "
                    "HomeAssistant URL is not available"
                ) from err

        webhook_path = webhook.async_generate_path(event_id)
        self._webhook_url = f"{base_url}{webhook_path}"

        if base_url.startswith("https"):
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                "https_webhook",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="https_webhook",
                translation_placeholders={
                    "base_url": base_url,
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
    ):
        """Handle incoming webhook from Reolink for inbound messages and calls."""

        _LOGGER.debug("Webhook '%s' called", webhook_id)

        if not request.body_exists:
            _LOGGER.debug("Webhook '%s' triggered without payload", webhook_id)
            return

        data = await request.text()
        if not data:
            _LOGGER.debug(
                "Webhook '%s' triggered with unknown payload: %s", webhook_id, data
            )
            return

        channels = await self._api.ONVIF_event_callback(data)

        if channels is None:
            async_dispatcher_send(hass, f"{webhook_id}_all", {})
        else:
            for channel in channels:
                async_dispatcher_send(hass, f"{webhook_id}_{channel}", {})
