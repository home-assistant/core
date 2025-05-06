"""Interface implementation for cloud client."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from http import HTTPStatus
import logging
from pathlib import Path
from typing import Any, Literal

import aiohttp
from hass_nabucasa.client import CloudClient as Interface, RemoteActivationNotAllowed
from webrtc_models import RTCIceServer

from homeassistant.components import google_assistant, persistent_notification, webhook
from homeassistant.components.alexa import (
    errors as alexa_errors,
    smart_home as alexa_smart_home,
)
from homeassistant.components.camera.webrtc import async_register_ice_servers
from homeassistant.components.google_assistant import smart_home as ga
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import Context, HassJob, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.util.aiohttp import MockRequest, serialize_response

from . import alexa_config, google_config
from .const import DISPATCHER_REMOTE_UPDATE, DOMAIN, PREF_ENABLE_CLOUD_ICE_SERVERS
from .prefs import CloudPreferences

_LOGGER = logging.getLogger(__name__)

VALID_REPAIR_TRANSLATION_KEYS = {
    "warn_bad_custom_domain_configuration",
    "reset_bad_custom_domain_configuration",
    "subscription_expired",
}


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
        self._alexa_config: alexa_config.CloudAlexaConfig | None = None
        self._google_config: google_config.CloudGoogleConfig | None = None
        self._alexa_config_init_lock = asyncio.Lock()
        self._google_config_init_lock = asyncio.Lock()
        self._relayer_region: str | None = None
        self._cloud_ice_servers_listener: Callable[[], None] | None = None

    @property
    def base_path(self) -> Path:
        """Return path to base dir."""
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
    def cloudhooks(self) -> dict[str, dict[str, str | bool]]:
        """Return list of cloudhooks."""
        return self._prefs.cloudhooks

    @property
    def remote_autostart(self) -> bool:
        """Return true if we want start a remote connection."""
        return self._prefs.remote_enabled

    @property
    def client_name(self) -> str:
        """Return the client name that will be used for API calls."""
        return SERVER_SOFTWARE

    @property
    def relayer_region(self) -> str | None:
        """Return the connected relayer region."""
        return self._relayer_region

    async def get_alexa_config(self) -> alexa_config.CloudAlexaConfig:
        """Return Alexa config."""
        if self._alexa_config is None:
            async with self._alexa_config_init_lock:
                if self._alexa_config is not None:
                    # This is reachable if the config was set while we waited
                    # for the lock
                    return self._alexa_config  # type: ignore[unreachable]

                cloud_user = await self._prefs.get_cloud_user()

                alexa_conf = alexa_config.CloudAlexaConfig(
                    self._hass,
                    self.alexa_user_config,
                    cloud_user,
                    self._prefs,
                    self.cloud,
                )
                await alexa_conf.async_initialize()
                self._alexa_config = alexa_conf

        return self._alexa_config

    async def get_google_config(self) -> google_config.CloudGoogleConfig:
        """Return Google config."""
        if not self._google_config:
            async with self._google_config_init_lock:
                if self._google_config is not None:
                    return self._google_config

                cloud_user = await self._prefs.get_cloud_user()

                google_conf = google_config.CloudGoogleConfig(
                    self._hass,
                    self.google_user_config,
                    cloud_user,
                    self._prefs,
                    self.cloud,
                )
                await google_conf.async_initialize()
                self._google_config = google_conf

        return self._google_config

    async def cloud_connected(self) -> None:
        """When cloud is connected."""
        _LOGGER.debug("cloud_connected")
        is_new_user = await self.prefs.async_set_username(self.cloud.username)

        async def enable_alexa(_: Any) -> None:
            """Enable Alexa."""
            aconf = await self.get_alexa_config()
            try:
                await aconf.async_enable_proactive_mode()
            except aiohttp.ClientError as err:  # If no internet available yet
                if self._hass.is_running:
                    logging.getLogger(__package__).warning(
                        (
                            "Unable to activate Alexa Report State: %s. Retrying in 30"
                            " seconds"
                        ),
                        err,
                    )
                async_call_later(self._hass, 30, enable_alexa_job)
            except (alexa_errors.NoTokenAvailable, alexa_errors.RequireRelink):
                pass

        enable_alexa_job = HassJob(enable_alexa, cancel_on_shutdown=True)

        async def enable_google(_: datetime) -> None:
            """Enable Google."""
            gconf = await self.get_google_config()

            gconf.async_enable_local_sdk()

            if gconf.should_report_state:
                gconf.async_enable_report_state()

            if is_new_user:
                await gconf.async_sync_entities(gconf.agent_user_id)

        async def setup_cloud_ice_servers(_: datetime) -> None:
            async def register_cloud_ice_server(
                ice_servers: list[RTCIceServer],
            ) -> Callable[[], None]:
                """Register cloud ice server."""

                def get_ice_servers() -> list[RTCIceServer]:
                    return ice_servers

                return async_register_ice_servers(self._hass, get_ice_servers)

            async def async_register_cloud_ice_servers_listener(
                prefs: CloudPreferences,
            ) -> None:
                is_cloud_ice_servers_enabled = (
                    self.cloud.is_logged_in
                    and not self.cloud.subscription_expired
                    and prefs.cloud_ice_servers_enabled
                )
                if is_cloud_ice_servers_enabled:
                    if self._cloud_ice_servers_listener is None:
                        self._cloud_ice_servers_listener = await self.cloud.ice_servers.async_register_ice_servers_listener(
                            register_cloud_ice_server
                        )
                elif self._cloud_ice_servers_listener:
                    self._cloud_ice_servers_listener()
                    self._cloud_ice_servers_listener = None

            async def async_prefs_updated(prefs: CloudPreferences) -> None:
                updated_prefs = prefs.last_updated

                if (
                    updated_prefs is None
                    or PREF_ENABLE_CLOUD_ICE_SERVERS not in updated_prefs
                ):
                    return

                await async_register_cloud_ice_servers_listener(prefs)

            await async_register_cloud_ice_servers_listener(self._prefs)

            self._prefs.async_listen_updates(async_prefs_updated)

        tasks = []

        if self._prefs.alexa_enabled and self._prefs.alexa_report_state:
            tasks.append(enable_alexa)

        if self._prefs.google_enabled:
            tasks.append(enable_google)

        tasks.append(setup_cloud_ice_servers)

        if tasks:
            await asyncio.gather(*(task(None) for task in tasks))

    async def cloud_disconnected(self) -> None:
        """When cloud disconnected."""
        _LOGGER.debug("cloud_disconnected")
        if self._google_config:
            self._google_config.async_disable_local_sdk()

    async def cloud_started(self) -> None:
        """When cloud is started."""

    async def cloud_stopped(self) -> None:
        """When the cloud is stopped."""

    async def logout_cleanups(self) -> None:
        """Cleanup some stuff after logout."""
        await self.prefs.async_set_username(None)

        if self._alexa_config:
            self._alexa_config.async_deinitialize()
        self._alexa_config = None

        if self._google_config:
            self._google_config.async_deinitialize()
        self._google_config = None

        if self._cloud_ice_servers_listener:
            self._cloud_ice_servers_listener()
            self._cloud_ice_servers_listener = None

    @callback
    def user_message(self, identifier: str, title: str, message: str) -> None:
        """Create a message for user to UI."""
        persistent_notification.async_create(self._hass, message, title, identifier)

    @callback
    def dispatcher_message(self, identifier: str, data: Any = None) -> None:
        """Match cloud notification to dispatcher."""
        if identifier.startswith("remote_"):
            async_dispatcher_send(self._hass, DISPATCHER_REMOTE_UPDATE, data)

    async def async_cloud_connect_update(self, connect: bool) -> None:
        """Process cloud remote message to client."""
        if not self._prefs.remote_allow_remote_enable:
            raise RemoteActivationNotAllowed
        await self._prefs.async_update(remote_enabled=connect)

    async def async_cloud_connection_info(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Process cloud connection info message to client."""
        return {
            "remote": {
                "can_enable": self._prefs.remote_allow_remote_enable,
                "connected": self.cloud.remote.is_connected,
                "enabled": self._prefs.remote_enabled,
                "instance_domain": self.cloud.remote.instance_domain,
                "alias": self.cloud.remote.alias,
            },
            "version": HA_VERSION,
            "instance_id": self.prefs.instance_id,
            "name": self._hass.config.location_name,
        }

    async def async_alexa_message(self, payload: dict[Any, Any]) -> dict[Any, Any]:
        """Process cloud alexa message to client."""
        cloud_user = await self._prefs.get_cloud_user()
        aconfig = await self.get_alexa_config()
        return await alexa_smart_home.async_handle_message(
            self._hass,
            aconfig,
            payload,
            context=Context(user_id=cloud_user),
            enabled=self._prefs.alexa_enabled,
        )

    async def async_google_message(self, payload: dict[Any, Any]) -> dict[Any, Any]:
        """Process cloud google message to client."""
        gconf = await self.get_google_config()

        msgid: Any = "<UNKNOWN>"
        if isinstance(payload, dict):
            msgid = payload.get("requestId")
        _LOGGER.debug("Received cloud message %s", msgid)

        if not self._prefs.google_enabled:
            return ga.api_disabled_response(  # type: ignore[no-any-return, no-untyped-call]
                payload, gconf.agent_user_id
            )

        return await ga.async_handle_message(  # type: ignore[no-any-return, no-untyped-call]
            self._hass,
            gconf,
            gconf.agent_user_id,
            gconf.cloud_user,
            payload,
            google_assistant.SOURCE_CLOUD,
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

        response = await webhook.async_handle_webhook(
            self._hass, found["webhook_id"], request
        )

        response_dict = serialize_response(response)
        body = response_dict.get("body")

        return {
            "body": body,
            "status": response_dict["status"],
            "headers": {"Content-Type": response.content_type},
        }

    async def async_system_message(self, payload: dict[Any, Any] | None) -> None:
        """Handle system messages."""
        if payload and (region := payload.get("region")):
            self._relayer_region = region

    async def async_cloudhooks_update(
        self, data: dict[str, dict[str, str | bool]]
    ) -> None:
        """Update local list of cloudhooks."""
        await self._prefs.async_update(cloudhooks=data)

    async def async_create_repair_issue(
        self,
        identifier: str,
        translation_key: str,
        *,
        placeholders: dict[str, str] | None = None,
        severity: Literal["error", "warning"] = "warning",
    ) -> None:
        """Create a repair issue."""
        if translation_key not in VALID_REPAIR_TRANSLATION_KEYS:
            raise ValueError(f"Invalid translation key {translation_key}")
        async_create_issue(
            hass=self._hass,
            domain=DOMAIN,
            issue_id=identifier,
            translation_key=translation_key,
            translation_placeholders=placeholders,
            severity=IssueSeverity(severity),
            is_fixable=False,
        )

    async def async_delete_repair_issue(self, identifier: str) -> None:
        """Delete a repair issue."""
        async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=identifier)
