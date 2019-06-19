"""Interface implementation for cloud client."""
import asyncio
from pathlib import Path
from typing import Any, Dict
from datetime import timedelta
import logging

import aiohttp
import async_timeout
from hass_nabucasa import cloud_api
from hass_nabucasa.client import CloudClient as Interface

from homeassistant.core import callback
from homeassistant.components.alexa import (
    config as alexa_config,
    errors as alexa_errors,
    smart_home as alexa_sh,
    entities as alexa_entities,
    state_report as alexa_state_report,
)
from homeassistant.components.google_assistant import (
    helpers as ga_h, smart_home as ga)
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import entity_registry
from homeassistant.util.aiohttp import MockRequest
from homeassistant.util.dt import utcnow

from . import utils
from .const import (
    CONF_ENTITY_CONFIG, CONF_FILTER, DOMAIN, DISPATCHER_REMOTE_UPDATE,
    PREF_SHOULD_EXPOSE, DEFAULT_SHOULD_EXPOSE,
    PREF_DISABLE_2FA, DEFAULT_DISABLE_2FA, RequireRelink)
from .prefs import CloudPreferences


_LOGGER = logging.getLogger(__name__)
# Time to wait when entity preferences have changed before syncing it to
# the cloud.
SYNC_DELAY = 1


class AlexaConfig(alexa_config.AbstractConfig):
    """Alexa Configuration."""

    def __init__(self, hass, config, prefs, cloud):
        """Initialize the Alexa config."""
        super().__init__(hass)
        self._config = config
        self._prefs = prefs
        self._cloud = cloud
        self._token = None
        self._token_valid = None
        self._cur_entity_prefs = prefs.alexa_entity_configs
        self._alexa_sync_unsub = None
        self._endpoint = None

        prefs.async_listen_updates(self._async_prefs_updated)
        hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED,
            self._handle_entity_registry_updated
        )

    @property
    def enabled(self):
        """Return if Alexa is enabled."""
        return self._prefs.alexa_enabled

    @property
    def supports_auth(self):
        """Return if config supports auth."""
        return True

    @property
    def should_report_state(self):
        """Return if states should be proactively reported."""
        return self._prefs.alexa_report_state

    @property
    def endpoint(self):
        """Endpoint for report state."""
        if self._endpoint is None:
            raise ValueError("No endpoint available. Fetch access token first")

        return self._endpoint

    @property
    def entity_config(self):
        """Return entity config."""
        return self._config.get(CONF_ENTITY_CONFIG, {})

    def should_expose(self, entity_id):
        """If an entity should be exposed."""
        if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        if not self._config[CONF_FILTER].empty_filter:
            return self._config[CONF_FILTER](entity_id)

        entity_configs = self._prefs.alexa_entity_configs
        entity_config = entity_configs.get(entity_id, {})
        return entity_config.get(
            PREF_SHOULD_EXPOSE, DEFAULT_SHOULD_EXPOSE)

    async def async_get_access_token(self):
        """Get an access token."""
        if self._token_valid is not None and self._token_valid < utcnow():
            return self._token

        resp = await cloud_api.async_alexa_access_token(self._cloud)
        body = await resp.json()

        if resp.status == 400:
            if body['reason'] in ('RefreshTokenNotFound', 'UnknownRegion'):
                raise RequireRelink

            raise alexa_errors.NoTokenAvailable

        self._token = body['access_token']
        self._endpoint = body['event_endpoint']
        self._token_valid = utcnow() + timedelta(seconds=body['expires_in'])
        return self._token

    async def _async_prefs_updated(self, prefs):
        """Handle updated preferences."""
        if self.should_report_state != self.is_reporting_states:
            if self.should_report_state:
                await self.async_enable_proactive_mode()
            else:
                await self.async_disable_proactive_mode()

        # If entity prefs are the same or we have filter in config.yaml,
        # don't sync.
        if (self._cur_entity_prefs is prefs.alexa_entity_configs or
                not self._config[CONF_FILTER].empty_filter):
            return

        if self._alexa_sync_unsub:
            self._alexa_sync_unsub()

        self._alexa_sync_unsub = async_call_later(
            self.hass, SYNC_DELAY, self._sync_prefs)

    async def _sync_prefs(self, _now):
        """Sync the updated preferences to Alexa."""
        self._alexa_sync_unsub = None
        old_prefs = self._cur_entity_prefs
        new_prefs = self._prefs.alexa_entity_configs

        seen = set()
        to_update = []
        to_remove = []

        for entity_id, info in old_prefs.items():
            seen.add(entity_id)
            old_expose = info.get(PREF_SHOULD_EXPOSE)

            if entity_id in new_prefs:
                new_expose = new_prefs[entity_id].get(PREF_SHOULD_EXPOSE)
            else:
                new_expose = None

            if old_expose == new_expose:
                continue

            if new_expose:
                to_update.append(entity_id)
            else:
                to_remove.append(entity_id)

        # Now all the ones that are in new prefs but never were in old prefs
        for entity_id, info in new_prefs.items():
            if entity_id in seen:
                continue

            new_expose = info.get(PREF_SHOULD_EXPOSE)

            if new_expose is None:
                continue

            # Only test if we should expose. It can never be a remove action,
            # as it didn't exist in old prefs object.
            if new_expose:
                to_update.append(entity_id)

        # We only set the prefs when update is successful, that way we will
        # retry when next change comes in.
        if await self._sync_helper(to_update, to_remove):
            self._cur_entity_prefs = new_prefs

    async def async_sync_entities(self):
        """Sync all entities to Alexa."""
        to_update = []
        to_remove = []

        for entity in alexa_entities.async_get_entities(self.hass, self):
            if self.should_expose(entity.entity_id):
                to_update.append(entity.entity_id)
            else:
                to_remove.append(entity.entity_id)

        return await self._sync_helper(to_update, to_remove)

    async def _sync_helper(self, to_update, to_remove) -> bool:
        """Sync entities to Alexa.

        Return boolean if it was successful.
        """
        if not to_update and not to_remove:
            return True

        tasks = []

        if to_update:
            tasks.append(alexa_state_report.async_send_add_or_update_message(
                self.hass, self, to_update
            ))

        if to_remove:
            tasks.append(alexa_state_report.async_send_delete_message(
                self.hass, self, to_remove
            ))

        try:
            with async_timeout.timeout(10):
                await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

            return True

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout trying to sync entitites to Alexa")
            return False

        except aiohttp.ClientError as err:
            _LOGGER.warning("Error trying to sync entities to Alexa: %s", err)
            return False

    async def _handle_entity_registry_updated(self, event):
        """Handle when entity registry updated."""
        if not self.enabled or not self._cloud.is_logged_in:
            return

        action = event.data['action']
        entity_id = event.data['entity_id']
        to_update = []
        to_remove = []

        if action == 'create' and self.should_expose(entity_id):
            to_update.append(entity_id)
        elif action == 'remove' and self.should_expose(entity_id):
            to_remove.append(entity_id)

        await self._sync_helper(to_update, to_remove)


class CloudClient(Interface):
    """Interface class for Home Assistant Cloud."""

    def __init__(self, hass: HomeAssistantType, prefs: CloudPreferences,
                 websession: aiohttp.ClientSession,
                 alexa_cfg: Dict[str, Any], google_config: Dict[str, Any]):
        """Initialize client interface to Cloud."""
        self._hass = hass
        self._prefs = prefs
        self._websession = websession
        self.google_user_config = google_config
        self.alexa_user_config = alexa_cfg
        self._alexa_config = None
        self._google_config = None
        self.cloud = None

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
    def alexa_config(self) -> AlexaConfig:
        """Return Alexa config."""
        if self._alexa_config is None:
            self._alexa_config = AlexaConfig(
                self._hass, self.alexa_user_config, self._prefs, self.cloud)

        return self._alexa_config

    @property
    def google_config(self) -> ga_h.Config:
        """Return Google config."""
        if not self._google_config:
            google_conf = self.google_user_config

            def should_expose(entity):
                """If an entity should be exposed."""
                if entity.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
                    return False

                if not google_conf['filter'].empty_filter:
                    return google_conf['filter'](entity.entity_id)

                entity_configs = self.prefs.google_entity_configs
                entity_config = entity_configs.get(entity.entity_id, {})
                return entity_config.get(
                    PREF_SHOULD_EXPOSE, DEFAULT_SHOULD_EXPOSE)

            def should_2fa(entity):
                """If an entity should be checked for 2FA."""
                entity_configs = self.prefs.google_entity_configs
                entity_config = entity_configs.get(entity.entity_id, {})
                return not entity_config.get(
                    PREF_DISABLE_2FA, DEFAULT_DISABLE_2FA)

            username = self._hass.data[DOMAIN].claims["cognito:username"]

            self._google_config = ga_h.Config(
                should_expose=should_expose,
                should_2fa=should_2fa,
                secure_devices_pin=self._prefs.google_secure_devices_pin,
                entity_config=google_conf.get(CONF_ENTITY_CONFIG),
                agent_user_id=username,
            )

        # Set it to the latest.
        self._google_config.secure_devices_pin = \
            self._prefs.google_secure_devices_pin

        return self._google_config

    async def async_initialize(self, cloud) -> None:
        """Initialize the client."""
        self.cloud = cloud

        if self.alexa_config.should_report_state and self.cloud.is_logged_in:
            await self.alexa_config.async_enable_proactive_mode()

    async def cleanups(self) -> None:
        """Cleanup some stuff after logout."""
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

        return await ga.async_handle_message(
            self._hass, self.google_config, self.prefs.cloud_user, payload
        )

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
