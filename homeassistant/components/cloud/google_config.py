"""Google config for Cloud."""
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.components.google_assistant.helpers import AbstractConfig

from .const import (
    PREF_SHOULD_EXPOSE,
    DEFAULT_SHOULD_EXPOSE,
    CONF_ENTITY_CONFIG,
    PREF_DISABLE_2FA,
    DEFAULT_DISABLE_2FA,
)


class CloudGoogleConfig(AbstractConfig):
    """HA Cloud Configuration for Google Assistant."""

    def __init__(self, config, prefs, cloud):
        """Initialize the Alexa config."""
        self._config = config
        self._prefs = prefs
        self._cloud = cloud

    @property
    def agent_user_id(self):
        """Return Agent User Id to use for query responses."""
        return self._cloud.claims["cognito:username"]

    @property
    def entity_config(self):
        """Return entity config."""
        return self._config.get(CONF_ENTITY_CONFIG) or {}

    @property
    def secure_devices_pin(self):
        """Return entity config."""
        return self._prefs.google_secure_devices_pin

    def should_expose(self, state):
        """If an entity should be exposed."""
        if state.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        if not self._config["filter"].empty_filter:
            return self._config["filter"](state.entity_id)

        entity_configs = self._prefs.google_entity_configs
        entity_config = entity_configs.get(state.entity_id, {})
        return entity_config.get(PREF_SHOULD_EXPOSE, DEFAULT_SHOULD_EXPOSE)

    def should_2fa(self, state):
        """If an entity should be checked for 2FA."""
        entity_configs = self._prefs.google_entity_configs
        entity_config = entity_configs.get(state.entity_id, {})
        return not entity_config.get(PREF_DISABLE_2FA, DEFAULT_DISABLE_2FA)
