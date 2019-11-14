"""Alexa entity adapters."""
from typing import List

from homeassistant.core import callback
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    CLOUD_NEVER_EXPOSED_ENTITIES,
    CONF_NAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.util.decorator import Registry
from homeassistant.components.climate import const as climate
from homeassistant.components import (
    alarm_control_panel,
    alert,
    automation,
    binary_sensor,
    cover,
    fan,
    group,
    input_boolean,
    light,
    lock,
    media_player,
    scene,
    script,
    sensor,
    switch,
)

from .const import CONF_DESCRIPTION, CONF_DISPLAY_CATEGORIES
from .capabilities import (
    AlexaBrightnessController,
    AlexaChannelController,
    AlexaColorController,
    AlexaColorTemperatureController,
    AlexaContactSensor,
    AlexaDoorbellEventSource,
    AlexaEndpointHealth,
    AlexaInputController,
    AlexaLockController,
    AlexaModeController,
    AlexaMotionSensor,
    AlexaPercentageController,
    AlexaPlaybackController,
    AlexaPlaybackStateReporter,
    AlexaPowerController,
    AlexaPowerLevelController,
    AlexaRangeController,
    AlexaSceneController,
    AlexaSecurityPanelController,
    AlexaSeekController,
    AlexaSpeaker,
    AlexaStepSpeaker,
    AlexaTemperatureSensor,
    AlexaThermostatController,
    AlexaToggleController,
)

ENTITY_ADAPTERS = Registry()

TRANSLATION_TABLE = dict.fromkeys(map(ord, r"}{\/|\"()[]+~!><*%"), None)


class DisplayCategory:
    """Possible display categories for Discovery response.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#display-categories
    """

    # Describes a combination of devices set to a specific state, when the
    # state change must occur in a specific order. For example, a "watch
    # Netflix" scene might require the: 1. TV to be powered on & 2. Input set
    # to HDMI1. Applies to Scenes
    ACTIVITY_TRIGGER = "ACTIVITY_TRIGGER"

    # Indicates media devices with video or photo capabilities.
    CAMERA = "CAMERA"

    # Indicates an endpoint that detects and reports contact.
    CONTACT_SENSOR = "CONTACT_SENSOR"

    # Indicates a door.
    DOOR = "DOOR"

    # Indicates a doorbell.
    DOORBELL = "DOORBELL"

    # Indicates a fan.
    FAN = "FAN"

    # Indicates light sources or fixtures.
    LIGHT = "LIGHT"

    # Indicates a microwave oven.
    MICROWAVE = "MICROWAVE"

    # Indicates an endpoint that detects and reports motion.
    MOTION_SENSOR = "MOTION_SENSOR"

    # An endpoint that cannot be described in on of the other categories.
    OTHER = "OTHER"

    # Describes a combination of devices set to a specific state, when the
    # order of the state change is not important. For example a bedtime scene
    # might include turning off lights and lowering the thermostat, but the
    # order is unimportant.    Applies to Scenes
    SCENE_TRIGGER = "SCENE_TRIGGER"

    # Indicates a security panel.
    SECURITY_PANEL = "SECURITY_PANEL"

    # Indicates an endpoint that locks.
    SMARTLOCK = "SMARTLOCK"

    # Indicates modules that are plugged into an existing electrical outlet.
    # Can control a variety of devices.
    SMARTPLUG = "SMARTPLUG"

    # Indicates the endpoint is a speaker or speaker system.
    SPEAKER = "SPEAKER"

    # Indicates in-wall switches wired to the electrical system.  Can control a
    # variety of devices.
    SWITCH = "SWITCH"

    # Indicates endpoints that report the temperature only.
    TEMPERATURE_SENSOR = "TEMPERATURE_SENSOR"

    # Indicates endpoints that control temperature, stand-alone air
    # conditioners, or heaters with direct temperature control.
    THERMOSTAT = "THERMOSTAT"

    # Indicates the endpoint is a television.
    TV = "TV"


class AlexaEntity:
    """An adaptation of an entity, expressed in Alexa's terms.

    The API handlers should manipulate entities only through this interface.
    """

    def __init__(self, hass, config, entity):
        """Initialize Alexa Entity."""
        self.hass = hass
        self.config = config
        self.entity = entity
        self.entity_conf = config.entity_config.get(entity.entity_id, {})

    @property
    def entity_id(self):
        """Return the Entity ID."""
        return self.entity.entity_id

    def friendly_name(self):
        """Return the Alexa API friendly name."""
        return self.entity_conf.get(CONF_NAME, self.entity.name).translate(
            TRANSLATION_TABLE
        )

    def description(self):
        """Return the Alexa API description."""
        description = self.entity_conf.get(CONF_DESCRIPTION) or self.entity_id
        return f"{description} via Home Assistant".translate(TRANSLATION_TABLE)

    def alexa_id(self):
        """Return the Alexa API entity id."""
        return self.entity.entity_id.replace(".", "#").translate(TRANSLATION_TABLE)

    def display_categories(self):
        """Return a list of display categories."""
        entity_conf = self.config.entity_config.get(self.entity.entity_id, {})
        if CONF_DISPLAY_CATEGORIES in entity_conf:
            return [entity_conf[CONF_DISPLAY_CATEGORIES]]
        return self.default_display_categories()

    def default_display_categories(self):
        """Return a list of default display categories.

        This can be overridden by the user in the Home Assistant configuration.

        See also DisplayCategory.
        """
        raise NotImplementedError

    def get_interface(self, capability):
        """Return the given AlexaInterface.

        Raises _UnsupportedInterface.
        """
        pass

    def interfaces(self):
        """Return a list of supported interfaces.

        Used for discovery. The list should contain AlexaInterface instances.
        If the list is empty, this entity will not be discovered.
        """
        raise NotImplementedError

    def serialize_properties(self):
        """Yield each supported property in API format."""
        for interface in self.interfaces():
            for prop in interface.serialize_properties():
                yield prop

    def serialize_discovery(self):
        """Serialize the entity for discovery."""
        return {
            "displayCategories": self.display_categories(),
            "cookie": {},
            "endpointId": self.alexa_id(),
            "friendlyName": self.friendly_name(),
            "description": self.description(),
            "manufacturerName": "Home Assistant",
            "capabilities": [i.serialize_discovery() for i in self.interfaces()],
        }


@callback
def async_get_entities(hass, config) -> List[AlexaEntity]:
    """Return all entities that are supported by Alexa."""
    entities = []
    for state in hass.states.async_all():
        if state.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            continue

        if state.domain not in ENTITY_ADAPTERS:
            continue

        alexa_entity = ENTITY_ADAPTERS[state.domain](hass, config, state)

        if not list(alexa_entity.interfaces()):
            continue

        entities.append(alexa_entity)

    return entities


@ENTITY_ADAPTERS.register(alert.DOMAIN)
@ENTITY_ADAPTERS.register(automation.DOMAIN)
@ENTITY_ADAPTERS.register(group.DOMAIN)
@ENTITY_ADAPTERS.register(input_boolean.DOMAIN)
class GenericCapabilities(AlexaEntity):
    """A generic, on/off device.

    The choice of last resort.
    """

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.OTHER]

    def interfaces(self):
        """Yield the supported interfaces."""
        return [
            AlexaPowerController(self.entity),
            AlexaEndpointHealth(self.hass, self.entity),
        ]


@ENTITY_ADAPTERS.register(switch.DOMAIN)
class SwitchCapabilities(AlexaEntity):
    """Class to represent Switch capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.SWITCH]

    def interfaces(self):
        """Yield the supported interfaces."""
        return [
            AlexaPowerController(self.entity),
            AlexaEndpointHealth(self.hass, self.entity),
        ]


@ENTITY_ADAPTERS.register(climate.DOMAIN)
class ClimateCapabilities(AlexaEntity):
    """Class to represent Climate capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.THERMOSTAT]

    def interfaces(self):
        """Yield the supported interfaces."""
        # If we support two modes, one being off, we allow turning on too.
        if climate.HVAC_MODE_OFF in self.entity.attributes.get(
            climate.ATTR_HVAC_MODES, []
        ):
            yield AlexaPowerController(self.entity)

        yield AlexaThermostatController(self.hass, self.entity)
        yield AlexaTemperatureSensor(self.hass, self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)


@ENTITY_ADAPTERS.register(cover.DOMAIN)
class CoverCapabilities(AlexaEntity):
    """Class to represent Cover capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.DOOR]

    def interfaces(self):
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & cover.SUPPORT_SET_POSITION:
            yield AlexaPercentageController(self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)


@ENTITY_ADAPTERS.register(light.DOMAIN)
class LightCapabilities(AlexaEntity):
    """Class to represent Light capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.LIGHT]

    def interfaces(self):
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)

        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & light.SUPPORT_BRIGHTNESS:
            yield AlexaBrightnessController(self.entity)
        if supported & light.SUPPORT_COLOR:
            yield AlexaColorController(self.entity)
        if supported & light.SUPPORT_COLOR_TEMP:
            yield AlexaColorTemperatureController(self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)


@ENTITY_ADAPTERS.register(fan.DOMAIN)
class FanCapabilities(AlexaEntity):
    """Class to represent Fan capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.FAN]

    def interfaces(self):
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & fan.SUPPORT_SET_SPEED:
            yield AlexaPercentageController(self.entity)
            yield AlexaPowerLevelController(self.entity)
            yield AlexaRangeController(
                self.entity, instance=f"{fan.DOMAIN}.{fan.ATTR_SPEED}"
            )

        if supported & fan.SUPPORT_OSCILLATE:
            yield AlexaToggleController(
                self.entity, instance=f"{fan.DOMAIN}.{fan.ATTR_OSCILLATING}"
            )
        if supported & fan.SUPPORT_DIRECTION:
            yield AlexaModeController(
                self.entity, instance=f"{fan.DOMAIN}.{fan.ATTR_DIRECTION}"
            )

        yield AlexaEndpointHealth(self.hass, self.entity)


@ENTITY_ADAPTERS.register(lock.DOMAIN)
class LockCapabilities(AlexaEntity):
    """Class to represent Lock capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.SMARTLOCK]

    def interfaces(self):
        """Yield the supported interfaces."""
        return [
            AlexaLockController(self.entity),
            AlexaEndpointHealth(self.hass, self.entity),
        ]


@ENTITY_ADAPTERS.register(media_player.const.DOMAIN)
class MediaPlayerCapabilities(AlexaEntity):
    """Class to represent MediaPlayer capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        device_class = self.entity.attributes.get(ATTR_DEVICE_CLASS)
        if device_class == media_player.DEVICE_CLASS_SPEAKER:
            return [DisplayCategory.SPEAKER]

        return [DisplayCategory.TV]

    def interfaces(self):
        """Yield the supported interfaces."""
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield AlexaPowerController(self.entity)

        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & media_player.const.SUPPORT_VOLUME_SET:
            yield AlexaSpeaker(self.entity)

        step_volume_features = (
            media_player.const.SUPPORT_VOLUME_MUTE
            | media_player.const.SUPPORT_VOLUME_STEP
        )
        if supported & step_volume_features:
            yield AlexaStepSpeaker(self.entity)

        playback_features = (
            media_player.const.SUPPORT_PLAY
            | media_player.const.SUPPORT_PAUSE
            | media_player.const.SUPPORT_STOP
            | media_player.const.SUPPORT_NEXT_TRACK
            | media_player.const.SUPPORT_PREVIOUS_TRACK
        )
        if supported & playback_features:
            yield AlexaPlaybackController(self.entity)
            yield AlexaPlaybackStateReporter(self.entity)

        if supported & media_player.const.SUPPORT_SEEK:
            yield AlexaSeekController(self.entity)

        if supported & media_player.SUPPORT_SELECT_SOURCE:
            yield AlexaInputController(self.entity)

        if supported & media_player.const.SUPPORT_PLAY_MEDIA:
            yield AlexaChannelController(self.entity)


@ENTITY_ADAPTERS.register(scene.DOMAIN)
class SceneCapabilities(AlexaEntity):
    """Class to represent Scene capabilities."""

    def description(self):
        """Return the Alexa API description."""
        description = AlexaEntity.description(self)
        if "scene" not in description.casefold():
            return f"{description} (Scene)"
        return description

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.SCENE_TRIGGER]

    def interfaces(self):
        """Yield the supported interfaces."""
        return [AlexaSceneController(self.entity, supports_deactivation=False)]


@ENTITY_ADAPTERS.register(script.DOMAIN)
class ScriptCapabilities(AlexaEntity):
    """Class to represent Script capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.ACTIVITY_TRIGGER]

    def interfaces(self):
        """Yield the supported interfaces."""
        can_cancel = bool(self.entity.attributes.get("can_cancel"))
        return [AlexaSceneController(self.entity, supports_deactivation=can_cancel)]


@ENTITY_ADAPTERS.register(sensor.DOMAIN)
class SensorCapabilities(AlexaEntity):
    """Class to represent Sensor capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        # although there are other kinds of sensors, all but temperature
        # sensors are currently ignored.
        return [DisplayCategory.TEMPERATURE_SENSOR]

    def interfaces(self):
        """Yield the supported interfaces."""
        attrs = self.entity.attributes
        if attrs.get(ATTR_UNIT_OF_MEASUREMENT) in (TEMP_FAHRENHEIT, TEMP_CELSIUS):
            yield AlexaTemperatureSensor(self.hass, self.entity)
            yield AlexaEndpointHealth(self.hass, self.entity)


@ENTITY_ADAPTERS.register(binary_sensor.DOMAIN)
class BinarySensorCapabilities(AlexaEntity):
    """Class to represent BinarySensor capabilities."""

    TYPE_CONTACT = "contact"
    TYPE_MOTION = "motion"

    def default_display_categories(self):
        """Return the display categories for this entity."""
        sensor_type = self.get_type()
        if sensor_type is self.TYPE_CONTACT:
            return [DisplayCategory.CONTACT_SENSOR]
        if sensor_type is self.TYPE_MOTION:
            return [DisplayCategory.MOTION_SENSOR]

    def interfaces(self):
        """Yield the supported interfaces."""
        sensor_type = self.get_type()
        if sensor_type is self.TYPE_CONTACT:
            yield AlexaContactSensor(self.hass, self.entity)
        elif sensor_type is self.TYPE_MOTION:
            yield AlexaMotionSensor(self.hass, self.entity)

        entity_conf = self.config.entity_config.get(self.entity.entity_id, {})
        if CONF_DISPLAY_CATEGORIES in entity_conf:
            if entity_conf[CONF_DISPLAY_CATEGORIES] == DisplayCategory.DOORBELL:
                yield AlexaDoorbellEventSource(self.entity)

        yield AlexaEndpointHealth(self.hass, self.entity)

    def get_type(self):
        """Return the type of binary sensor."""
        attrs = self.entity.attributes
        if attrs.get(ATTR_DEVICE_CLASS) in ("door", "garage_door", "opening", "window"):
            return self.TYPE_CONTACT
        if attrs.get(ATTR_DEVICE_CLASS) == "motion":
            return self.TYPE_MOTION


@ENTITY_ADAPTERS.register(alarm_control_panel.DOMAIN)
class AlarmControlPanelCapabilities(AlexaEntity):
    """Class to represent Alarm capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.SECURITY_PANEL]

    def interfaces(self):
        """Yield the supported interfaces."""
        if not self.entity.attributes.get("code_arm_required"):
            yield AlexaSecurityPanelController(self.hass, self.entity)
            yield AlexaEndpointHealth(self.hass, self.entity)
