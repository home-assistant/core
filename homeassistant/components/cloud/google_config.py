"""Google config for Cloud."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any

from hass_nabucasa import Cloud, cloud_api
from hass_nabucasa.google_report_state import ErrorResponse

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.google_assistant import DOMAIN as GOOGLE_DOMAIN
from homeassistant.components.google_assistant.helpers import AbstractConfig
from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
    async_get_assistant_settings,
    async_get_entity_settings,
    async_listen_entity_updates,
    async_set_assistant_option,
    async_should_expose,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.core import (
    CoreState,
    Event,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er, start
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.entityfilter import EntityFilter
from homeassistant.setup import async_setup_component

from .const import (
    CONF_ENTITY_CONFIG,
    CONF_FILTER,
    DEFAULT_DISABLE_2FA,
    DOMAIN,
    PREF_DISABLE_2FA,
    PREF_SHOULD_EXPOSE,
)
from .prefs import GOOGLE_SETTINGS_VERSION, CloudPreferences

if TYPE_CHECKING:
    from .client import CloudClient

_LOGGER = logging.getLogger(__name__)

CLOUD_GOOGLE = f"{DOMAIN}.{GOOGLE_DOMAIN}"


SUPPORTED_DOMAINS = {
    "alarm_control_panel",
    "button",
    "camera",
    "climate",
    "cover",
    "fan",
    "group",
    "humidifier",
    "input_boolean",
    "input_button",
    "input_select",
    "light",
    "lock",
    "media_player",
    "scene",
    "script",
    "select",
    "switch",
    "vacuum",
}

SUPPORTED_BINARY_SENSOR_DEVICE_CLASSES = {
    BinarySensorDeviceClass.DOOR,
    BinarySensorDeviceClass.GARAGE_DOOR,
    BinarySensorDeviceClass.LOCK,
    BinarySensorDeviceClass.MOTION,
    BinarySensorDeviceClass.OPENING,
    BinarySensorDeviceClass.PRESENCE,
    BinarySensorDeviceClass.WINDOW,
}

SUPPORTED_SENSOR_DEVICE_CLASSES = {
    SensorDeviceClass.AQI,
    SensorDeviceClass.CO,
    SensorDeviceClass.CO2,
    SensorDeviceClass.HUMIDITY,
    SensorDeviceClass.PM10,
    SensorDeviceClass.PM25,
    SensorDeviceClass.TEMPERATURE,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
}


def _supported_legacy(hass: HomeAssistant, entity_id: str) -> bool:
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


class CloudGoogleConfig(AbstractConfig):
    """HA Cloud Configuration for Google Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        cloud_user: str,
        prefs: CloudPreferences,
        cloud: Cloud[CloudClient],
    ) -> None:
        """Initialize the Google config."""
        super().__init__(hass)
        self._config = config
        self._user = cloud_user
        self._prefs = prefs
        self._cloud = cloud
        self._sync_entities_lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        """Return if Google is enabled."""
        return (
            self._cloud.is_logged_in
            and not self._cloud.subscription_expired
            and self._prefs.google_enabled
        )

    @property
    def entity_config(self) -> dict[str, Any]:
        """Return entity config."""
        return self._config.get(CONF_ENTITY_CONFIG) or {}

    @property
    def secure_devices_pin(self) -> str | None:
        """Return entity config."""
        return self._prefs.google_secure_devices_pin

    @property
    def should_report_state(self) -> bool:
        """Return if states should be proactively reported."""
        return self.enabled and self._prefs.google_report_state

    def get_local_webhook_id(self, agent_user_id: Any) -> str:
        """Return the webhook ID to be used for actions for a given agent user id via the local SDK."""
        return self._prefs.google_local_webhook_id

    def get_local_user_id(self, webhook_id: Any) -> str:
        """Map webhook ID to a Home Assistant user ID.

        Any action initiated by Google Assistant via the local SDK will be attributed
        to the returned user ID.
        """
        return self._user

    @property
    def cloud_user(self) -> str:
        """Return Cloud User account."""
        return self._user

    def _migrate_google_entity_settings_v1(self) -> None:
        """Migrate Google entity settings to entity registry options."""
        if not self._config[CONF_FILTER].empty_filter:
            # Don't migrate if there's a YAML config
            return

        for entity_id in {
            *self.hass.states.async_entity_ids(),
            *self._prefs.google_entity_configs,
        }:
            async_expose_entity(
                self.hass,
                CLOUD_GOOGLE,
                entity_id,
                self._should_expose_legacy(entity_id),
            )
            if _2fa_disabled := (self._2fa_disabled_legacy(entity_id) is not None):
                async_set_assistant_option(
                    self.hass,
                    CLOUD_GOOGLE,
                    entity_id,
                    PREF_DISABLE_2FA,
                    _2fa_disabled,
                )

    async def async_initialize(self) -> None:
        """Perform async initialization of config."""
        _LOGGER.debug("async_initialize")
        await super().async_initialize()

        async def on_hass_started(hass: HomeAssistant) -> None:
            _LOGGER.debug("async_initialize on_hass_started")
            if self._prefs.google_settings_version != GOOGLE_SETTINGS_VERSION:
                _LOGGER.info(
                    "Start migration of Google Assistant settings from v%s to v%s",
                    self._prefs.google_settings_version,
                    GOOGLE_SETTINGS_VERSION,
                )
                if self._prefs.google_settings_version < 2 or (
                    # Recover from a bug we had in 2023.5.0 where entities didn't get exposed
                    self._prefs.google_settings_version < 3
                    and not any(
                        settings.get("should_expose", False)
                        for settings in async_get_assistant_settings(
                            hass, CLOUD_GOOGLE
                        ).values()
                    )
                ):
                    self._migrate_google_entity_settings_v1()

                _LOGGER.info(
                    "Finished migration of Google Assistant settings from v%s to v%s",
                    self._prefs.google_settings_version,
                    GOOGLE_SETTINGS_VERSION,
                )
                await self._prefs.async_update(
                    google_settings_version=GOOGLE_SETTINGS_VERSION
                )
            self._on_deinitialize.append(
                async_listen_entity_updates(
                    self.hass, CLOUD_GOOGLE, self._async_exposed_entities_updated
                )
            )

        async def on_hass_start(hass: HomeAssistant) -> None:
            _LOGGER.debug("async_initialize on_hass_start")
            if self.enabled and GOOGLE_DOMAIN not in self.hass.config.components:
                await async_setup_component(self.hass, GOOGLE_DOMAIN, {})

        self._on_deinitialize.append(start.async_at_start(self.hass, on_hass_start))
        self._on_deinitialize.append(start.async_at_started(self.hass, on_hass_started))

        self._on_deinitialize.append(
            self._prefs.async_listen_updates(self._async_prefs_updated)
        )
        self._on_deinitialize.append(
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                self._handle_entity_registry_updated,
            )
        )
        self._on_deinitialize.append(
            self.hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                self._handle_device_registry_updated,
            )
        )

    def should_expose(self, state: State) -> bool:
        """If a state object should be exposed."""
        return self._should_expose_entity_id(state.entity_id)

    def _should_expose_legacy(self, entity_id: str) -> bool:
        """If an entity ID should be exposed."""
        if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        entity_configs = self._prefs.google_entity_configs
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

        default_expose = self._prefs.google_default_expose

        # Backwards compat
        if default_expose is None:
            return not auxiliary_entity and _supported_legacy(self.hass, entity_id)

        return (
            not auxiliary_entity
            and split_entity_id(entity_id)[0] in default_expose
            and _supported_legacy(self.hass, entity_id)
        )

    def _should_expose_entity_id(self, entity_id: str) -> bool:
        """If an entity should be exposed."""
        entity_filter: EntityFilter = self._config[CONF_FILTER]
        if not entity_filter.empty_filter:
            if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
                return False
            return entity_filter(entity_id)

        return async_should_expose(self.hass, CLOUD_GOOGLE, entity_id)

    @property
    def agent_user_id(self) -> str:
        """Return Agent User Id to use for query responses."""
        return self._cloud.username

    @property
    def has_registered_user_agent(self) -> bool:
        """Return if we have a Agent User Id registered."""
        return len(self.async_get_agent_users()) > 0

    def get_agent_user_id_from_context(self, context: Any) -> str:
        """Get agent user ID making request."""
        return self.agent_user_id

    def get_agent_user_id_from_webhook(self, webhook_id: str) -> str | None:
        """Map webhook ID to a Google agent user ID.

        Return None if no agent user id is found for the webhook_id.
        """
        if webhook_id != self._prefs.google_local_webhook_id:
            return None

        return self.agent_user_id

    def _2fa_disabled_legacy(self, entity_id: str) -> bool | None:
        """If an entity should be checked for 2FA."""
        entity_configs = self._prefs.google_entity_configs
        entity_config = entity_configs.get(entity_id, {})
        return entity_config.get(PREF_DISABLE_2FA)

    def should_2fa(self, state: State) -> bool:
        """If an entity should be checked for 2FA."""
        try:
            settings = async_get_entity_settings(self.hass, state.entity_id)
        except HomeAssistantError:
            # Handle the entity has been removed
            return False

        assistant_options = settings.get(CLOUD_GOOGLE, {})
        return not assistant_options.get(PREF_DISABLE_2FA, DEFAULT_DISABLE_2FA)

    async def async_report_state(
        self, message: Any, agent_user_id: str, event_id: str | None = None
    ) -> None:
        """Send a state report to Google."""
        try:
            await self._cloud.google_report_state.async_send_message(message)
        except ErrorResponse as err:
            _LOGGER.warning("Error reporting state - %s: %s", err.code, err.message)

    async def _async_request_sync_devices(self, agent_user_id: str) -> HTTPStatus | int:
        """Trigger a sync with Google."""
        if self._sync_entities_lock.locked():
            return HTTPStatus.OK

        async with self._sync_entities_lock:
            resp = await cloud_api.async_google_actions_request_sync(self._cloud)
            return resp.status

    async def async_connect_agent_user(self, agent_user_id: str) -> None:
        """Add a synced and known agent_user_id.

        Called before sending a sync response to Google.
        """
        await self._prefs.async_update(google_connected=True)

    async def async_disconnect_agent_user(self, agent_user_id: str) -> None:
        """Turn off report state and disable further state reporting.

        Called when:
         - The user disconnects their account from Google.
         - When the cloud configuration is initialized
         - When sync entities fails with 404
        """
        await self._prefs.async_update(google_connected=False)

    @callback
    def async_get_agent_users(self) -> tuple:
        """Return known agent users."""
        if (
            not self._cloud.is_logged_in  # Can't call Cloud.username if not logged in
            or not self._prefs.google_connected
            or not self._cloud.username
        ):
            return ()
        return (self._cloud.username,)

    async def _async_prefs_updated(self, prefs: CloudPreferences) -> None:
        """Handle updated preferences."""
        _LOGGER.debug("_async_prefs_updated")
        if not self._cloud.is_logged_in:
            if self.is_reporting_state:
                self.async_disable_report_state()
            if self.is_local_sdk_active:
                self.async_disable_local_sdk()
            return

        if (
            self.enabled
            and GOOGLE_DOMAIN not in self.hass.config.components
            and self.hass.is_running
        ):
            await async_setup_component(self.hass, GOOGLE_DOMAIN, {})

        sync_entities = False

        if self.should_report_state != self.is_reporting_state:
            if self.should_report_state:
                self.async_enable_report_state()
            else:
                self.async_disable_report_state()

            # State reporting is reported as a property on entities.
            # So when we change it, we need to sync all entities.
            sync_entities = True

        if self.enabled and not self.is_local_sdk_active:
            self.async_enable_local_sdk()
            sync_entities = True
        elif not self.enabled and self.is_local_sdk_active:
            self.async_disable_local_sdk()
            sync_entities = True

        if sync_entities and self.hass.is_running:
            await self.async_sync_entities_all()

    @callback
    def _async_exposed_entities_updated(self) -> None:
        """Handle updated preferences."""
        self.async_schedule_google_sync_all()

    @callback
    def _handle_entity_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Handle when entity registry updated."""
        if (
            not self.enabled
            or not self._cloud.is_logged_in
            or self.hass.state is not CoreState.running
        ):
            return

        # Only consider entity registry updates if info relevant for Google has changed
        if event.data["action"] == "update" and not bool(
            set(event.data["changes"]) & er.ENTITY_DESCRIBING_ATTRIBUTES
        ):
            return

        entity_id = event.data["entity_id"]

        if not self._should_expose_entity_id(entity_id):
            return

        self.async_schedule_google_sync_all()

    @callback
    def _handle_device_registry_updated(
        self, event: Event[dr.EventDeviceRegistryUpdatedData]
    ) -> None:
        """Handle when device registry updated."""
        if (
            not self.enabled
            or not self._cloud.is_logged_in
            or self.hass.state is not CoreState.running
        ):
            return

        # Device registry is only used for area changes. All other changes are ignored.
        if event.data["action"] != "update" or "area_id" not in event.data["changes"]:
            return

        # Check if any exposed entity uses the device area
        if not any(
            entity_entry.area_id is None
            and self._should_expose_entity_id(entity_entry.entity_id)
            for entity_entry in er.async_entries_for_device(
                er.async_get(self.hass), event.data["device_id"]
            )
        ):
            return

        self.async_schedule_google_sync_all()
