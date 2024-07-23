"""Provides the Toon DataUpdateCoordinator."""

from __future__ import annotations

import logging
import secrets

from toonapi import Status, Toon, ToonError

from homeassistant.components import cloud, webhook
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CLOUDHOOK_URL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ToonDataUpdateCoordinator(DataUpdateCoordinator[Status]):
    """Class to manage fetching Toon data from single endpoint."""

    def __init__(
        self, hass: HomeAssistant, *, entry: ConfigEntry, session: OAuth2Session
    ) -> None:
        """Initialize global Toon data updater."""
        self.session = session
        self.entry = entry

        async def async_token_refresh() -> str:
            await session.async_ensure_token_valid()
            return session.token["access_token"]

        self.toon = Toon(
            token=session.token["access_token"],
            session=async_get_clientsession(hass),
            token_refresh_method=async_token_refresh,
        )

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def register_webhook(self, event: Event | None = None) -> None:
        """Register a webhook with Toon to get live updates."""
        if CONF_WEBHOOK_ID not in self.entry.data:
            data = {**self.entry.data, CONF_WEBHOOK_ID: secrets.token_hex()}
            self.hass.config_entries.async_update_entry(self.entry, data=data)

        if cloud.async_active_subscription(self.hass):
            if CONF_CLOUDHOOK_URL not in self.entry.data:
                try:
                    webhook_url = await cloud.async_create_cloudhook(
                        self.hass, self.entry.data[CONF_WEBHOOK_ID]
                    )
                except cloud.CloudNotConnected:
                    webhook_url = webhook.async_generate_url(
                        self.hass, self.entry.data[CONF_WEBHOOK_ID]
                    )
                else:
                    data = {**self.entry.data, CONF_CLOUDHOOK_URL: webhook_url}
                    self.hass.config_entries.async_update_entry(self.entry, data=data)
            else:
                webhook_url = self.entry.data[CONF_CLOUDHOOK_URL]
        else:
            webhook_url = webhook.async_generate_url(
                self.hass, self.entry.data[CONF_WEBHOOK_ID]
            )

        # Ensure the webhook is not registered already
        webhook_unregister(self.hass, self.entry.data[CONF_WEBHOOK_ID])

        webhook_register(
            self.hass,
            DOMAIN,
            "Toon",
            self.entry.data[CONF_WEBHOOK_ID],
            self.handle_webhook,
        )

        try:
            await self.toon.subscribe_webhook(
                application_id=self.entry.entry_id, url=webhook_url
            )
            _LOGGER.info("Registered Toon webhook: %s", webhook_url)
        except ToonError as err:
            _LOGGER.error("Error during webhook registration - %s", err)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.unregister_webhook
        )

    async def handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request
    ) -> None:
        """Handle webhook callback."""
        try:
            data = await request.json()
        except ValueError:
            return

        _LOGGER.debug("Got webhook data: %s", data)

        # Webhook expired notification, re-register
        if data.get("code") == 510:
            await self.register_webhook()
            return

        if (
            "updateDataSet" not in data
            or "commonName" not in data
            or self.data.agreement.display_common_name != data["commonName"]
        ):
            _LOGGER.warning("Received invalid data from Toon webhook - %s", data)
            return

        try:
            await self.toon.update(data["updateDataSet"])
            self.async_update_listeners()
        except ToonError as err:
            _LOGGER.error("Could not process data received from Toon webhook - %s", err)

    async def unregister_webhook(self, event: Event | None = None) -> None:
        """Remove / Unregister webhook for toon."""
        _LOGGER.debug(
            "Unregistering Toon webhook (%s)", self.entry.data[CONF_WEBHOOK_ID]
        )
        try:
            await self.toon.unsubscribe_webhook(self.entry.entry_id)
        except ToonError as err:
            _LOGGER.error("Failed unregistering Toon webhook - %s", err)

        webhook_unregister(self.hass, self.entry.data[CONF_WEBHOOK_ID])

    async def _async_update_data(self) -> Status:
        """Fetch data from Toon."""
        try:
            return await self.toon.update()
        except ToonError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
