"""Alexa configuration for Home Assistant Cloud."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from hass_nabucasa import Cloud, cloud_api
from yarl import URL

from homeassistant.components import persistent_notification
from homeassistant.components.alexa import (
    DOMAIN as ALEXA_DOMAIN,
    config as alexa_config,
    entities as alexa_entities,
    errors as alexa_errors,
    state_report as alexa_state_report,
)
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
    async_get_assistant_settings,
    async_listen_entity_updates,
    async_should_expose,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.core import Event, HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, start
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.entityfilter import EntityFilter
from homeassistant.helpers.event import async_call_later
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .const import (
    CONF_ENTITY_CONFIG,
    CONF_FILTER,
    DOMAIN as CLOUD_DOMAIN,
    PREF_ALEXA_REPORT_STATE,
    PREF_ENABLE_ALEXA,
    PREF_SHOULD_EXPOSE,
)
from .prefs import ALEXA_SETTINGS_VERSION, CloudPreferences

if TYPE_CHECKING:
    from .client import CloudClient

_LOGGER = logging.getLogger(__name__)

CLOUD_ALEXA = f"{CLOUD_DOMAIN}.{ALEXA_DOMAIN}"

# Time to wait when entity preferences have changed before syncing it to
# the cloud.
SYNC_DELAY = 1


SUPPORTED_DOMAINS = {
    "alarm_control_panel",
    "alert",
    "automation",
    "button",
    "camera",
    "climate",
    "cover",
    "fan",
    "group",
    "humidifier",
    "image_processing",
    "input_boolean",
    "input_button",
    "input_number",
    "light",
    "lock",
    "media_player",
    "number",
    "scene",
    "script",
    "switch",
    "timer",
    "vacuum",
}

SUPPORTED_BINARY_SENSOR_DEVICE_CLASSES = {
    BinarySensorDeviceClass.DOOR,
    BinarySensorDeviceClass.GARAGE_DOOR,
    BinarySensorDeviceClass.MOTION,
    BinarySensorDeviceClass.OPENING,
    BinarySensorDeviceClass.PRESENCE,
    BinarySensorDeviceClass.WINDOW,
}

SUPPORTED_SENSOR_DEVICE_CLASSES = {
    SensorDeviceClass.TEMPERATURE,
}


def entity_supported(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the entity is supported.

    This is called when migrating from legacy config format to avoid exposing
    all binary sensors and sensors.
    """
    domain = split_entity_id(entity_id)[0]
    if domain in SUPPORTED_DOMAINS:
        return True

    try:
        device_class = get_device_class(hass, entity_id)
    except HomeAssistantError:
        # The entity no longer exists
        return False
    if (
        domain == "binary_sensor"
        and device_class in SUPPORTED_BINARY_SENSOR_DEVICE_CLASSES
    ):
        return True

    if domain == "sensor" and device_class in SUPPORTED_SENSOR_DEVICE_CLASSES:
        return True

    return False


class CloudAlexaConfig(alexa_config.AbstractConfig):
    """Alexa Configuration."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        cloud_user: str,
        prefs: CloudPreferences,
        cloud: Cloud[CloudClient],
    ) -> None:
        """Initialize the Alexa config."""
        super().__init__(hass)
        self._config = config
        self._cloud_user = cloud_user
        self._prefs = prefs
        self._cloud = cloud
        self._token = None
        self._token_valid: datetime | None = None
        self._cur_entity_prefs = async_get_assistant_settings(hass, CLOUD_ALEXA)
        self._alexa_sync_unsub: Callable[[], None] | None = None
        self._endpoint: str | URL | None = None

    @property
    def enabled(self) -> bool:
        """Return if Alexa is enabled."""
        return (
            self._cloud.is_logged_in
            and not self._cloud.subscription_expired
            and self._prefs.alexa_enabled
        )

    @property
    def supports_auth(self) -> bool:
        """Return if config supports auth."""
        return True

    @property
    def should_report_state(self) -> bool:
        """Return if states should be proactively reported."""
        return (
            self._prefs.alexa_enabled
            and self._prefs.alexa_report_state
            and self.authorized
        )

    @property
    def endpoint(self) -> str | URL | None:
        """Endpoint for report state."""
        if self._endpoint is None:
            raise ValueError("No endpoint available. Fetch access token first")

        return self._endpoint

    @property
    def locale(self) -> str:
        """Return config locale."""
        # Not clear how to determine locale atm.
        return "en-US"

    @property
    def entity_config(self) -> dict[str, Any]:
        """Return entity config."""
        return self._config.get(CONF_ENTITY_CONFIG) or {}

    @callback
    def user_identifier(self) -> str:
        """Return an identifier for the user that represents this config."""
        return self._cloud_user

    def _migrate_alexa_entity_settings_v1(self) -> None:
        """Migrate alexa entity settings to entity registry options."""
        if not self._config[CONF_FILTER].empty_filter:
            # Don't migrate if there's a YAML config
            return

        for entity_id in {
            *self.hass.states.async_entity_ids(),
            *self._prefs.alexa_entity_configs,
        }:
            async_expose_entity(
                self.hass,
                CLOUD_ALEXA,
                entity_id,
                self._should_expose_legacy(entity_id),
            )

    async def async_initialize(self) -> None:
        """Initialize the Alexa config."""
        await super().async_initialize()

        async def on_hass_started(hass: HomeAssistant) -> None:
            if self._prefs.alexa_settings_version != ALEXA_SETTINGS_VERSION:
                _LOGGER.info(
                    "Start migration of Alexa settings from v%s to v%s",
                    self._prefs.alexa_settings_version,
                    ALEXA_SETTINGS_VERSION,
                )
                if self._prefs.alexa_settings_version < 2 or (
                    # Recover from a bug we had in 2023.5.0 where entities didn't get exposed
                    self._prefs.alexa_settings_version < 3
                    and not any(
                        settings.get("should_expose", False)
                        for settings in async_get_assistant_settings(
                            hass, CLOUD_ALEXA
                        ).values()
                    )
                ):
                    self._migrate_alexa_entity_settings_v1()

                _LOGGER.info(
                    "Finished migration of Alexa settings from v%s to v%s",
                    self._prefs.alexa_settings_version,
                    ALEXA_SETTINGS_VERSION,
                )
                await self._prefs.async_update(
                    alexa_settings_version=ALEXA_SETTINGS_VERSION
                )
            async_listen_entity_updates(
                self.hass, CLOUD_ALEXA, self._async_exposed_entities_updated
            )

        async def on_hass_start(hass: HomeAssistant) -> None:
            if self.enabled and ALEXA_DOMAIN not in self.hass.config.components:
                await async_setup_component(self.hass, ALEXA_DOMAIN, {})

        start.async_at_start(self.hass, on_hass_start)
        start.async_at_started(self.hass, on_hass_started)

        self._prefs.async_listen_updates(self._async_prefs_updated)
        self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._handle_entity_registry_updated,
        )

    def _should_expose_legacy(self, entity_id: str) -> bool:
        """If an entity should be exposed."""
        if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        entity_configs = self._prefs.alexa_entity_configs
        entity_config = entity_configs.get(entity_id, {})
        entity_expose: bool | None = entity_config.get(PREF_SHOULD_EXPOSE)
        if entity_expose is not None:
            return entity_expose

        entity_registry = er.async_get(self.hass)
        if registry_entry := entity_registry.async_get(entity_id):
            auxiliary_entity = (
                registry_entry.entity_category is not None
                or registry_entry.hidden_by is not None
            )
        else:
            auxiliary_entity = False

        # Backwards compat
        if (default_expose := self._prefs.alexa_default_expose) is None:
            return not auxiliary_entity and entity_supported(self.hass, entity_id)

        return (
            not auxiliary_entity
            and split_entity_id(entity_id)[0] in default_expose
            and entity_supported(self.hass, entity_id)
        )

    @callback
    def should_expose(self, entity_id: str) -> bool:
        """If an entity should be exposed."""
        entity_filter: EntityFilter = self._config[CONF_FILTER]
        if not entity_filter.empty_filter:
            if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
                return False
            return entity_filter(entity_id)

        return async_should_expose(self.hass, CLOUD_ALEXA, entity_id)

    @callback
    def async_invalidate_access_token(self) -> None:
        """Invalidate access token."""
        self._token_valid = None

    async def async_get_access_token(self) -> str | None:
        """Get an access token."""
        if self._token_valid is not None and self._token_valid > utcnow():
            return self._token

        resp = await cloud_api.async_alexa_access_token(self._cloud)
        body = await resp.json()

        if resp.status == HTTPStatus.BAD_REQUEST:
            if body["reason"] in ("RefreshTokenNotFound", "UnknownRegion"):
                if self.should_report_state:
                    persistent_notification.async_create(
                        self.hass,
                        (
                            "There was an error reporting state to Alexa"
                            f" ({body['reason']}). Please re-link your Alexa skill via"
                            " the Alexa app to continue using it."
                        ),
                        "Alexa state reporting disabled",
                        "cloud_alexa_report",
                    )
                raise alexa_errors.RequireRelink

            raise alexa_errors.NoTokenAvailable

        self._token = body["access_token"]
        self._endpoint = body["event_endpoint"]
        self._token_valid = utcnow() + timedelta(seconds=body["expires_in"])
        return self._token

    async def _async_prefs_updated(self, prefs: CloudPreferences) -> None:
        """Handle updated preferences."""
        if not self._cloud.is_logged_in:
            if self.is_reporting_states:
                await self.async_disable_proactive_mode()

            if self._alexa_sync_unsub:
                self._alexa_sync_unsub()
                self._alexa_sync_unsub = None
            return

        updated_prefs = prefs.last_updated

        if (
            ALEXA_DOMAIN not in self.hass.config.components
            and self.enabled
            and self.hass.is_running
        ):
            await async_setup_component(self.hass, ALEXA_DOMAIN, {})

        if self.should_report_state != self.is_reporting_states:
            if self.should_report_state:
                try:
                    await self.async_enable_proactive_mode()
                except (alexa_errors.NoTokenAvailable, alexa_errors.RequireRelink):
                    await self.set_authorized(False)
            else:
                await self.async_disable_proactive_mode()

            # State reporting is reported as a property on entities.
            # So when we change it, we need to sync all entities.
            await self.async_sync_entities()
            return

        # Nothing to do if no Alexa related things have changed
        if not any(
            key in updated_prefs
            for key in (
                PREF_ALEXA_REPORT_STATE,
                PREF_ENABLE_ALEXA,
            )
        ):
            return

        await self.async_sync_entities()

    @callback
    def _async_exposed_entities_updated(self) -> None:
        """Handle updated preferences."""
        # Delay updating as we might update more
        if self._alexa_sync_unsub:
            self._alexa_sync_unsub()

        self._alexa_sync_unsub = async_call_later(
            self.hass, SYNC_DELAY, self._sync_prefs
        )

    async def _sync_prefs(self, _now: datetime) -> None:
        """Sync the updated preferences to Alexa."""
        self._alexa_sync_unsub = None
        old_prefs = self._cur_entity_prefs
        new_prefs = async_get_assistant_settings(self.hass, CLOUD_ALEXA)

        seen = set()
        to_update = []
        to_remove = []
        is_enabled = self.enabled

        for entity_id, info in old_prefs.items():
            seen.add(entity_id)

            if not is_enabled:
                to_remove.append(entity_id)

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

    async def async_sync_entities(self) -> bool:
        """Sync all entities to Alexa."""
        # Remove any pending sync
        if self._alexa_sync_unsub:
            self._alexa_sync_unsub()
            self._alexa_sync_unsub = None

        to_update = []
        to_remove = []

        is_enabled = self.enabled

        for entity in alexa_entities.async_get_entities(self.hass, self):
            if is_enabled and self.should_expose(entity.entity_id):
                to_update.append(entity.entity_id)
            else:
                to_remove.append(entity.entity_id)

        return await self._sync_helper(to_update, to_remove)

    async def _sync_helper(self, to_update: list[str], to_remove: list[str]) -> bool:
        """Sync entities to Alexa.

        Return boolean if it was successful.
        """
        if not to_update and not to_remove:
            return True

        # Make sure it's valid.
        await self.async_get_access_token()

        tasks = []

        if to_update:
            tasks.append(
                asyncio.create_task(
                    alexa_state_report.async_send_add_or_update_message(
                        self.hass, self, to_update
                    )
                )
            )

        if to_remove:
            tasks.append(
                asyncio.create_task(
                    alexa_state_report.async_send_delete_message(
                        self.hass, self, to_remove
                    )
                )
            )

        try:
            async with asyncio.timeout(10):
                await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

            return True

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout trying to sync entities to Alexa")
            return False

        except aiohttp.ClientError as err:
            _LOGGER.warning("Error trying to sync entities to Alexa: %s", err)
            return False

    async def _handle_entity_registry_updated(self, event: Event) -> None:
        """Handle when entity registry updated."""
        if not self.enabled or not self._cloud.is_logged_in:
            return

        entity_id = event.data["entity_id"]

        if not self.should_expose(entity_id):
            return

        action = event.data["action"]
        to_update = []
        to_remove = []

        if action == "create":
            to_update.append(entity_id)
        elif action == "remove":
            to_remove.append(entity_id)
        elif action == "update" and bool(
            set(event.data["changes"]) & er.ENTITY_DESCRIBING_ATTRIBUTES
        ):
            to_update.append(entity_id)
            if "old_entity_id" in event.data:
                to_remove.append(event.data["old_entity_id"])

        with suppress(alexa_errors.NoTokenAvailable):
            await self._sync_helper(to_update, to_remove)
