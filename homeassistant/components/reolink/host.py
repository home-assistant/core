"""This component encapsulates the NVR/camera API and subscription."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
from aiohttp.web import Request
from reolink_aio.api import Host
from reolink_aio.exceptions import (
    ApiError,
    CredentialsInvalidError,
    InvalidContentTypeError,
)

from homeassistant.components import webhook
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CONF_PROTOCOL,
    CONF_USE_HTTPS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SUBSCRIPTION_RENEW_THRESHOLD,
)

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

    @property
    def unique_id(self) -> str:
        """Create the unique ID, base for all entities."""
        return self._unique_id

    @property
    def api(self):
        """Return the API object."""
        return self._api

    async def async_init(self) -> bool:
        """Connect to Reolink host."""
        self._api.expire_session()

        if not await self._api.get_host_data():
            return False

        if self._api.mac_address is None:
            return False

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
            if not await self._api.set_net_port(
                enable_onvif=enable_onvif,
                enable_rtmp=enable_rtmp,
                enable_rtsp=enable_rtsp,
            ):
                if enable_onvif:
                    _LOGGER.error(
                        "Failed to enable ONVIF on %s. Set it to ON to receive notifications",
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

        if not await self.register_webhook():
            return False

        await self.subscribe()

        return True

    async def update_states(self) -> bool:
        """Call the API of the camera device to update the states."""
        return await self._api.get_states()

    async def disconnect(self):
        """Disconnect from the API, so the connection will be released."""
        await self._api.unsubscribe_all()

        try:
            await self._api.logout()
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error(
                "Reolink connection error while logging out for host %s:%s: %s",
                self._api.host,
                self._api.port,
                str(err),
            )
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Reolink connection timeout while logging out for host %s:%s",
                self._api.host,
                self._api.port,
            )
        except ApiError as err:
            _LOGGER.error(
                "Reolink API error while logging out for host %s:%s: %s",
                self._api.host,
                self._api.port,
                str(err),
            )
        except CredentialsInvalidError:
            _LOGGER.error(
                "Reolink credentials error while logging out for host %s:%s",
                self._api.host,
                self._api.port,
            )
        except InvalidContentTypeError as err:
            _LOGGER.error(
                "Reolink content type error while logging out for host %s:%s: %s",
                self._api.host,
                self._api.port,
                str(err),
            )

    async def stop(self, event=None):
        """Disconnect the API."""
        await self.unregister_webhook()
        await self.disconnect()

    async def subscribe(self) -> bool:
        """Subscribe to motion events and register the webhook as a callback."""
        if self.webhook_id is None:
            if not self.register_webhook():
                return False

        if self._api.subscribed:
            _LOGGER.debug(
                "Host %s: is already subscribed to webhook %s",
                self._api.host,
                self._webhook_url,
            )
            return True

        if await self._api.subscribe(self._webhook_url):
            _LOGGER.info(
                "Host %s: subscribed successfully to webhook %s",
                self._api.host,
                self._webhook_url,
            )
        else:
            _LOGGER.error("Host %s: webhook subscription failed", self._api.host)
            return False

        return True

    async def renew(self) -> bool:
        """Renew the subscription of the motion events (lease time is set to 15 minutes)."""

        if not self._api.subscribed:
            _LOGGER.debug(
                "Host %s: requested to renew a non-existing Reolink subscription, trying to subscribe from scratch",
                self._api.host,
            )
            return await self.subscribe()

        timer = self._api.renewtimer
        if timer <= 0:
            _LOGGER.debug(
                "Host %s: Reolink subscription expired, trying to subscribe again",
                self._api.host,
            )
            return await self._api.subscribe(self._webhook_url)
        if timer <= SUBSCRIPTION_RENEW_THRESHOLD:
            if not await self._api.renew():
                _LOGGER.debug(
                    "Host %s: error renewing Reolink subscription, trying to subscribe again",
                    self._api.host,
                )
                return await self._api.subscribe(self._webhook_url)
            _LOGGER.info(
                "Host %s SUCCESSFULLY renewed Reolink subscription", self._api.host
            )

        return True

    async def register_webhook(self) -> bool:
        """Register the webhook for motion events."""
        self.webhook_id = f"reolink_{self.unique_id.replace(':', '')}"
        event_id = self.webhook_id

        try:
            webhook.async_register(
                self._hass, DOMAIN, event_id, self.webhook_id, self.handle_webhook
            )
        except ValueError:
            _LOGGER.debug(
                "Error registering webhook %s. Trying to unregister it first and re-register again",
                self.webhook_id,
            )
            webhook.async_unregister(self._hass, self.webhook_id)
            try:
                webhook.async_register(
                    self._hass, DOMAIN, event_id, self.webhook_id, self.handle_webhook
                )
            except ValueError:
                _LOGGER.error(
                    "Error registering a webhook %s for %s",
                    self.webhook_id,
                    self.api.nvr_name,
                )
                self.webhook_id = None
                return False

        try:
            base_url = get_url(self._hass, prefer_external=False)
        except NoURLAvailableError:
            try:
                base_url = get_url(self._hass, prefer_external=True)
            except NoURLAvailableError:
                _LOGGER.error(
                    "Error registering URL for webhook %s: HomeAssistant URL is not available",
                    self.webhook_id,
                )
                webhook.async_unregister(self._hass, self.webhook_id)
                self.webhook_id = None
                return False

        webhook_path = webhook.async_generate_path(self.webhook_id)
        self._webhook_url = f"{base_url}{webhook_path}"

        _LOGGER.info("Registered webhook: %s", self.webhook_id)
        return True

    async def unregister_webhook(self):
        """Unregister the webhook for motion events."""
        if self.webhook_id:
            _LOGGER.info("Unregistering webhook %s", self.webhook_id)
            webhook.async_unregister(self._hass, self.webhook_id)
        self.webhook_id = None

    async def handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: Request
    ):
        """Handle incoming webhook from Reolink for inbound messages and calls."""

        _LOGGER.debug("Webhook '%s' called", webhook_id)

        if not request.body_exists:
            _LOGGER.debug("Webhook '%s' triggered without payload", webhook_id)

        data = await request.text()
        if not data:
            _LOGGER.debug(
                "Webhook '%s' triggered with unknown payload: %s", webhook_id, data
            )
            return

        channel = await self._api.ONVIF_event_callback(data)

        if channel is None:
            hass.bus.async_fire(f"{webhook_id}_all", {})
        else:
            hass.bus.async_fire(f"{webhook_id}_{channel}", {})
