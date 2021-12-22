"""Support for MQTT scenes."""
import functools

import voluptuous as vol

from homeassistant.components import scene
from homeassistant.components.scene import Scene
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_PAYLOAD_ON, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from . import PLATFORMS
from .. import mqtt
from .const import CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN, DOMAIN
from .mixins import (
    CONF_OBJECT_ID,
    MQTT_AVAILABILITY_SCHEMA,
    MqttAvailability,
    MqttDiscoveryUpdate,
    async_setup_entry_helper,
    init_entity_id_from_config,
)

DEFAULT_NAME = "MQTT Scene"
DEFAULT_RETAIN = False

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_OBJECT_ID): cv.string,
    }
).extend(MQTT_AVAILABILITY_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT scene through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT scene dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, scene.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT scene."""
    async_add_entities([MqttScene(hass, config, config_entry, discovery_data)])


class MqttScene(
    MqttAvailability,
    MqttDiscoveryUpdate,
    Scene,
):
    """Representation of a scene that can be activated using MQTT."""

    _entity_id_format = scene.DOMAIN + ".{}"

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT scene."""
        self.hass = hass
        self._state = False
        self._sub_state = None

        self._unique_id = config.get(CONF_UNIQUE_ID)

        # Load config
        self._setup_from_config(config)

        # Initialize entity_id from config
        self._init_entity_id()

        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_data, self.discovery_update)

    def _init_entity_id(self):
        """Set entity_id from object_id if defined in config."""
        init_entity_id_from_config(
            self.hass, self, self._config, self._entity_id_format
        )

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = DISCOVERY_SCHEMA(discovery_payload)
        self._setup_from_config(config)
        await self.availability_discovery_update(config)
        self.async_write_ha_state()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._config = config

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        await MqttAvailability.async_will_remove_from_hass(self)
        await MqttDiscoveryUpdate.async_will_remove_from_hass(self)

    @property
    def name(self):
        """Return the name of the scene."""
        return self._config[CONF_NAME]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon."""
        return self._config.get(CONF_ICON)

    async def async_activate(self, **kwargs):
        """Activate the scene.

        This method is a coroutine.
        """
        await mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_ON],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
