"""Interface implementation for cloud client."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
from pathlib import Path
from typing import Any

import aiohttp
from hass_nabucasa.client import CloudClient as Interface

from homeassistant.components.alexa import (
    errors as alexa_errors,
    smart_home as alexa_sh,
)
from homeassistant.components.google_assistant import const as gc, smart_home as ga
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.util.aiohttp import MockRequest

from . import alexa_config, google_config, utils
from .const import DISPATCHER_REMOTE_UPDATE, DOMAIN
from .prefs import CloudPreferences


class CloudClient(Interface):
    """Interface class for Home Assistant Cloud."""

    def __init__(
        self,
        hass: HomeAssistant,
        prefs: CloudPreferences,
        websession: aiohttp.ClientSession,
        alexa_user_config: dict[str, Any],
        google_user_config: dict[str, Any],
    ) -> None:
        """Initialize client interface to Cloud."""
        self._hass = hass
        self._prefs = prefs
        self._websession = websession
        self.google_user_config = google_user_config
        self.alexa_user_config = alexa_user_config
        self._alexa_config: alexa_config.AlexaConfig | None = None
        self._google_config: google_config.CloudGoogleConfig | None = None

    @property
    def base_path(self) -> Path:
        """Return path to base dir."""
        assert self._hass.config.config_dir is not None
        return Path(self._hass.config.config_dir)

    @property
    def prefs(self) -> CloudPreferences:
        """Return Cloud preferences."""
        return self._prefs

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Return client loop."""
        return self._hass.loop

    @property
    def websession(self) -> aiohttp.ClientSession:
        """Return client session for aiohttp."""
        return self._websession

    @property
    def aiohttp_runner(self) -> aiohttp.web.AppRunner | None:
        """Return client webinterface aiohttp application."""
        return self._hass.http.runner

    @property
    def cloudhooks(self) -> dict[str, dict[str, str]]:
        """Return list of cloudhooks."""
        return self._prefs.cloudhooks

    @property
    def remote_autostart(self) -> bool:
        """Return true if we want start a remote connection."""
        return self._prefs.remote_enabled

    async def get_alexa_config(self) -> alexa_config.AlexaConfig:
        """Return Alexa config."""
        if self._alexa_config is None:
            assert self.cloud is not None

            cloud_user = await self._prefs.get_cloud_user()

            self._alexa_config = alexa_config.AlexaConfig(
                self._hass, self.alexa_user_config, cloud_user, self._prefs, self.cloud
            )
            await self._alexa_config.async_initialize()

        return self._alexa_config

    async def get_google_config(self) -> google_config.CloudGoogleConfig:
        """Return Google config."""
        if not self._google_config:
            assert self.cloud is not None

            cloud_user = await self._prefs.get_cloud_user()

            self._google_config = google_config.CloudGoogleConfig(
                self._hass, self.google_user_config, cloud_user, self._prefs, self.cloud
            )
            await self._google_config.async_initialize()

        return self._google_config

    async def cloud_started(self) -> None:
        """When cloud is started."""
        is_new_user = await self.prefs.async_set_username(self.cloud.username)

        async def enable_alexa(_):
            """Enable Alexa."""
            aconf = await self.get_alexa_config()
            try:
                await aconf.async_enable_proactive_mode()
            except aiohttp.ClientError as err:  # If no internet available yet
                if self._hass.is_running:
                    logging.getLogger(__package__).warning(
                        "Unable to activate Alexa Report State: %s. Retrying in 30 seconds",
                        err,
                    )
                async_call_later(self._hass, 30, enable_alexa)
            except alexa_errors.NoTokenAvailable:
                pass

        async def enable_google(_):
            """Enable Google."""
            gconf = await self.get_google_config()

            gconf.async_enable_local_sdk()

            if gconf.should_report_state:
                gconf.async_enable_report_state()

            if is_new_user:
                await gconf.async_sync_entities(gconf.agent_user_id)

        tasks = []

        if self._prefs.alexa_enabled and self._prefs.alexa_report_state:
            tasks.append(enable_alexa)

        if self._prefs.google_enabled:
            tasks.append(enable_google)

        if tasks:
            await asyncio.gather(*(task(None) for task in tasks))

    async def cloud_stopped(self) -> None:
        """When the cloud is stopped."""

    async def logout_cleanups(self) -> None:
        """Cleanup some stuff after logout."""
        await self.prefs.async_set_username(None)

        self._google_config = None

    @callback
    def user_message(self, identifier: str, title: str, message: str) -> None:
        """Create a message for user to UI."""
        self._hass.components.persistent_notification.async_create(
            message, title, identifier
        )

    @callback
    def dispatcher_message(self, identifier: str, data: Any = None) -> None:
        """Match cloud notification to dispatcher."""
        if identifier.startswith("remote_"):
            async_dispatcher_send(self._hass, DISPATCHER_REMOTE_UPDATE, data)

    async def async_cloud_connect_update(self, connect: bool) -> None:
        """Process cloud remote message to client."""
        await self._prefs.async_update(remote_enabled=connect)

    async def async_alexa_message(self, payload: dict[Any, Any]) -> dict[Any, Any]:
        """Process cloud alexa message to client."""
        cloud_user = await self._prefs.get_cloud_user()
        aconfig = await self.get_alexa_config()
        return await alexa_sh.async_handle_message(
            self._hass,
            aconfig,
            payload,
            context=Context(user_id=cloud_user),
            enabled=self._prefs.alexa_enabled,
        )

    async def async_google_message(self, payload: dict[Any, Any]) -> dict[Any, Any]:
        """Process cloud google message to client."""
        if not self._prefs.google_enabled:
            return ga.turned_off_response(payload)

        gconf = await self.get_google_config()

        return await ga.async_handle_message(
            self._hass, gconf, gconf.cloud_user, payload, gc.SOURCE_CLOUD
        )

    async def async_webhook_message(self, payload: dict[Any, Any]) -> dict[Any, Any]:
        """Process cloud webhook message to client."""
        cloudhook_id = payload["cloudhook_id"]

        found = None
        for cloudhook in self._prefs.cloudhooks.values():
            if cloudhook["cloudhook_id"] == cloudhook_id:
                found = cloudhook
                break

        if found is None:
            return {"status": HTTPStatus.OK}

        request = MockRequest(
            content=payload["body"].encode("utf-8"),
            headers=payload["headers"],
            method=payload["method"],
            query_string=payload["query"],
            mock_source=DOMAIN,
        )

        response = await self._hass.components.webhook.async_handle_webhook(
            found["webhook_id"], request
        )

        response_dict = utils.aiohttp_serialize_response(response)
        body = response_dict.get("body")

        return {
            "body": body,
            "status": response_dict["status"],
            "headers": {"Content-Type": response.content_type},
        }

    async def async_cloudhooks_update(self, data: dict[str, dict[str, str]]) -> None:
        """Update local list of cloudhooks."""
        await self._prefs.async_update(cloudhooks=data)
