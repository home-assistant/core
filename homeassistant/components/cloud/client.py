"""Interface implementation for cloud client."""
import asyncio
from pathlib import Path
from typing import Any, Dict

import aiohttp
from hass_nabucasa.client import CloudClient as Interface

from homeassistant.core import callback
from homeassistant.components.alexa import smart_home as alexa_sh
from homeassistant.components.google_assistant import (
    helpers as ga_h, smart_home as ga)
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.aiohttp import MockRequest

from . import utils
from .const import (
    CONF_ENTITY_CONFIG, CONF_FILTER, DOMAIN, DISPATCHER_REMOTE_UPDATE)
from .prefs import CloudPreferences


class CloudClient(Interface):
    """Interface class for Home Assistant Cloud."""

    def __init__(self, hass: HomeAssistantType, prefs: CloudPreferences,
                 websession: aiohttp.ClientSession,
                 alexa_config: Dict[str, Any], google_config: Dict[str, Any]):
        """Initialize client interface to Cloud."""
        self._hass = hass
        self._prefs = prefs
        self._websession = websession
        self._alexa_user_config = alexa_config
        self._google_user_config = google_config

        self._alexa_config = None
        self._google_config = None

    @property
    def base_path(self) -> Path:
        """Return path to base dir."""
        return Path(self._hass.config.config_dir)

    @property
    def prefs(self) -> CloudPreferences:
        """Return Cloud preferences."""
        return self._prefs

    @property
    def loop(self) -> asyncio.BaseEventLoop:
        """Return client loop."""
        return self._hass.loop

    @property
    def websession(self) -> aiohttp.ClientSession:
        """Return client session for aiohttp."""
        return self._websession

    @property
    def aiohttp_runner(self) -> aiohttp.web.AppRunner:
        """Return client webinterface aiohttp application."""
        return self._hass.http.runner

    @property
    def cloudhooks(self) -> Dict[str, Dict[str, str]]:
        """Return list of cloudhooks."""
        return self._prefs.cloudhooks

    @property
    def remote_autostart(self) -> bool:
        """Return true if we want start a remote connection."""
        return self._prefs.remote_enabled

    @property
    def alexa_config(self) -> alexa_sh.Config:
        """Return Alexa config."""
        if not self._alexa_config:
            alexa_conf = self._alexa_user_config

            self._alexa_config = alexa_sh.Config(
                endpoint=None,
                async_get_access_token=None,
                should_expose=alexa_conf[CONF_FILTER],
                entity_config=alexa_conf.get(CONF_ENTITY_CONFIG),
            )

        return self._alexa_config

    @property
    def google_config(self) -> ga_h.Config:
        """Return Google config."""
        if not self._google_config:
            google_conf = self._google_user_config

            def should_expose(entity):
                """If an entity should be exposed."""
                if entity.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
                    return False

                return google_conf['filter'](entity.entity_id)

            self._google_config = ga_h.Config(
                should_expose=should_expose,
                secure_devices_pin=self._prefs.google_secure_devices_pin,
                entity_config=google_conf.get(CONF_ENTITY_CONFIG),
            )

        # Set it to the latest.
        self._google_config.secure_devices_pin = \
            self._prefs.google_secure_devices_pin

        return self._google_config

    @property
    def google_user_config(self) -> Dict[str, Any]:
        """Return google action user config."""
        return self._google_user_config

    async def cleanups(self) -> None:
        """Cleanup some stuff after logout."""
        self._alexa_config = None
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

    async def async_alexa_message(
            self, payload: Dict[Any, Any]) -> Dict[Any, Any]:
        """Process cloud alexa message to client."""
        return await alexa_sh.async_handle_message(
            self._hass, self.alexa_config, payload,
            enabled=self._prefs.alexa_enabled
        )

    async def async_google_message(
            self, payload: Dict[Any, Any]) -> Dict[Any, Any]:
        """Process cloud google message to client."""
        if not self._prefs.google_enabled:
            return ga.turned_off_response(payload)

        answer = await ga.async_handle_message(
            self._hass, self.google_config, self.prefs.cloud_user, payload
        )

        # Fix AgentUserId
        try:
            cloud = self._hass.data[DOMAIN]
            answer['payload']['agentUserId'] = cloud.claims['cognito:username']
        except (TypeError, KeyError):
            return ga.turned_off_response(payload)

        return answer

    async def async_webhook_message(
            self, payload: Dict[Any, Any]) -> Dict[Any, Any]:
        """Process cloud webhook message to client."""
        cloudhook_id = payload['cloudhook_id']

        found = None
        for cloudhook in self._prefs.cloudhooks.values():
            if cloudhook['cloudhook_id'] == cloudhook_id:
                found = cloudhook
                break

        if found is None:
            return {
                'status': 200
            }

        request = MockRequest(
            content=payload['body'].encode('utf-8'),
            headers=payload['headers'],
            method=payload['method'],
            query_string=payload['query'],
        )

        response = await self._hass.components.webhook.async_handle_webhook(
            found['webhook_id'], request)

        response_dict = utils.aiohttp_serialize_response(response)
        body = response_dict.get('body')

        return {
            'body': body,
            'status': response_dict['status'],
            'headers': {
                'Content-Type': response.content_type
            }
        }

    async def async_cloudhooks_update(
            self, data: Dict[str, Dict[str, str]]) -> None:
        """Update local list of cloudhooks."""
        await self._prefs.async_update(cloudhooks=data)
