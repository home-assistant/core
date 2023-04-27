"""Google config for Cloud."""
import asyncio
from http import HTTPStatus
import logging
from typing import Any

from hass_nabucasa import Cloud, cloud_api
from hass_nabucasa.google_report_state import ErrorResponse

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.google_assistant import DOMAIN as GOOGLE_DOMAIN
from homeassistant.components.google_assistant.helpers import AbstractConfig
from homeassistant.components.homeassistant.exposed_entities import (
    async_listen_entity_updates,
    async_should_expose,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.core import (
    CoreState,
    Event,
    HomeAssistant,
    callback,
    split_entity_id,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er, start
from homeassistant.helpers.entity import get_device_class
from homeassistant.setup import async_setup_component

from .const import (
    CONF_ENTITY_CONFIG,
    CONF_FILTER,
    DEFAULT_DISABLE_2FA,
    DOMAIN as CLOUD_DOMAIN,
    PREF_DISABLE_2FA,
    PREF_SHOULD_EXPOSE,
)
from .prefs import GOOGLE_SETTINGS_VERSION, CloudPreferences

_LOGGER = logging.getLogger(__name__)

CLOUD_GOOGLE = f"{CLOUD_DOMAIN}.{GOOGLE_DOMAIN}"


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

    device_class = get_device_class(hass, entity_id)
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
        cloud: Cloud,
    ) -> None:
        """Initialize the Google config."""
        super().__init__(hass)
        self._config = config
        self._user = cloud_user
        self._prefs = prefs
        self._cloud = cloud
        self._sync_entities_lock = asyncio.Lock()

    @property
    def enabled(self):
        """Return if Google is enabled."""
        return (
            self._cloud.is_logged_in
            and not self._cloud.subscription_expired
            and self._prefs.google_enabled
        )

    @property
    def entity_config(self):
        """Return entity config."""
        return self._config.get(CONF_ENTITY_CONFIG) or {}

    @property
    def secure_devices_pin(self):
        """Return entity config."""
        return self._prefs.google_secure_devices_pin

    @property
    def should_report_state(self):
        """Return if states should be proactively reported."""
        return self.enabled and self._prefs.google_report_state

    def get_local_webhook_id(self, agent_user_id):
        """Return the webhook ID to be used for actions for a given agent user id via the local SDK."""
        return self._prefs.google_local_webhook_id

    def get_local_agent_user_id(self, webhook_id):
        """Return the user ID to be used for actions received via the local SDK."""
        return self._user

    @property
    def cloud_user(self):
        """Return Cloud User account."""
        return self._user

    def _migrate_google_entity_settings_v1(self):
        """Migrate Google entity settings to entity registry options."""
        if not self._config[CONF_FILTER].empty_filter:
            # Don't migrate if there's a YAML config
            return

        entity_registry = er.async_get(self.hass)

        for entity_id, entry in entity_registry.entities.items():
            if CLOUD_GOOGLE in entry.options:
                continue
            options = {"should_expose": self._should_expose_legacy(entity_id)}
            if _2fa_disabled := (self._2fa_disabled_legacy(entity_id) is not None):
                options[PREF_DISABLE_2FA] = _2fa_disabled
            entity_registry.async_update_entity_options(
                entity_id, CLOUD_GOOGLE, options
            )

    async def async_initialize(self):
        """Perform async initialization of config."""
        await super().async_initialize()

        if self._prefs.google_settings_version != GOOGLE_SETTINGS_VERSION:
            if self._prefs.google_settings_version < 2:
                self._migrate_google_entity_settings_v1()
            await self._prefs.async_update(
                google_settings_version=GOOGLE_SETTINGS_VERSION
            )

        async def hass_started(hass):
            if self.enabled and GOOGLE_DOMAIN not in self.hass.config.components:
                await async_setup_component(self.hass, GOOGLE_DOMAIN, {})

        start.async_at_start(self.hass, hass_started)

        # Remove any stored user agent id that is not ours
        remove_agent_user_ids = []
        for agent_user_id in self._store.agent_user_ids:
            if agent_user_id != self.agent_user_id:
                remove_agent_user_ids.append(agent_user_id)

        for agent_user_id in remove_agent_user_ids:
            await self.async_disconnect_agent_user(agent_user_id)

        self._prefs.async_listen_updates(self._async_prefs_updated)
        async_listen_entity_updates(
            self.hass, CLOUD_GOOGLE, self._async_exposed_entities_updated
        )
        self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._handle_entity_registry_updated,
        )
        self.hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            self._handle_device_registry_updated,
        )

    def should_expose(self, state):
        """If a state object should be exposed."""
        return self._should_expose_entity_id(state.entity_id)

    def _should_expose_legacy(self, entity_id):
        """If an entity ID should be exposed."""
        if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        entity_configs = self._prefs.google_entity_configs
        entity_config = entity_configs.get(entity_id, {})
        entity_expose = entity_config.get(PREF_SHOULD_EXPOSE)
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

    def _should_expose_entity_id(self, entity_id):
        """If an entity should be exposed."""
        if not self._config[CONF_FILTER].empty_filter:
            if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
                return False
            return self._config[CONF_FILTER](entity_id)

        return async_should_expose(self.hass, CLOUD_GOOGLE, entity_id)

    @property
    def agent_user_id(self):
        """Return Agent User Id to use for query responses."""
        return self._cloud.username

    @property
    def has_registered_user_agent(self):
        """Return if we have a Agent User Id registered."""
        return len(self._store.agent_user_ids) > 0

    def get_agent_user_id(self, context):
        """Get agent user ID making request."""
        return self.agent_user_id

    def _2fa_disabled_legacy(self, entity_id):
        """If an entity should be checked for 2FA."""
        entity_configs = self._prefs.google_entity_configs
        entity_config = entity_configs.get(entity_id, {})
        return entity_config.get(PREF_DISABLE_2FA)

    def should_2fa(self, state):
        """If an entity should be checked for 2FA."""
        entity_registry = er.async_get(self.hass)

        registry_entry = entity_registry.async_get(state.entity_id)
        if not registry_entry:
            # Handle the entity has been removed
            return False

        assistant_options = registry_entry.options.get(CLOUD_GOOGLE, {})
        return not assistant_options.get(PREF_DISABLE_2FA, DEFAULT_DISABLE_2FA)

    async def async_report_state(self, message, agent_user_id: str):
        """Send a state report to Google."""
        try:
            await self._cloud.google_report_state.async_send_message(message)
        except ErrorResponse as err:
            _LOGGER.warning("Error reporting state - %s: %s", err.code, err.message)

    async def _async_request_sync_devices(self, agent_user_id: str):
        """Trigger a sync with Google."""
        if self._sync_entities_lock.locked():
            return HTTPStatus.OK

        async with self._sync_entities_lock:
            resp = await cloud_api.async_google_actions_request_sync(self._cloud)
            return resp.status

    async def _async_prefs_updated(self, prefs):
        """Handle updated preferences."""
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
    def _handle_entity_registry_updated(self, event: Event) -> None:
        """Handle when entity registry updated."""
        if (
            not self.enabled
            or not self._cloud.is_logged_in
            or self.hass.state != CoreState.running
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
    def _handle_device_registry_updated(self, event: Event) -> None:
        """Handle when device registry updated."""
        if (
            not self.enabled
            or not self._cloud.is_logged_in
            or self.hass.state != CoreState.running
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
