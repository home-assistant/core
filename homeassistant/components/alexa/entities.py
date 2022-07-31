"""Alexa entity adapters."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components import (
    alarm_control_panel,
    alert,
    automation,
    binary_sensor,
    button,
    camera,
    cover,
    fan,
    group,
    image_processing,
    input_boolean,
    input_button,
    input_number,
    light,
    lock,
    media_player,
    scene,
    script,
    sensor,
    switch,
    timer,
    vacuum,
)
from homeassistant.components.climate import const as climate
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    CLOUD_NEVER_EXPOSED_ENTITIES,
    CONF_DESCRIPTION,
    CONF_NAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    __version__,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import network
from homeassistant.helpers.entity import entity_sources
from homeassistant.util.decorator import Registry

from .capabilities import (
    Alexa,
    AlexaBrightnessController,
    AlexaCameraStreamController,
    AlexaCapability,
    AlexaChannelController,
    AlexaColorController,
    AlexaColorTemperatureController,
    AlexaContactSensor,
    AlexaDoorbellEventSource,
    AlexaEndpointHealth,
    AlexaEqualizerController,
    AlexaEventDetectionSensor,
    AlexaInputController,
    AlexaLockController,
    AlexaModeController,
    AlexaMotionSensor,
    AlexaPlaybackController,
    AlexaPlaybackStateReporter,
    AlexaPowerController,
    AlexaRangeController,
    AlexaSceneController,
    AlexaSecurityPanelController,
    AlexaSeekController,
    AlexaSpeaker,
    AlexaStepSpeaker,
    AlexaTemperatureSensor,
    AlexaThermostatController,
    AlexaTimeHoldController,
    AlexaToggleController,
)
from .const import CONF_DISPLAY_CATEGORIES

if TYPE_CHECKING:
    from .config import AbstractConfig

_LOGGER = logging.getLogger(__name__)

ENTITY_ADAPTERS: Registry[str, type[AlexaEntity]] = Registry()

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

    # Indicates a device that emits pleasant odors and masks unpleasant odors in interior spaces.
    AIR_FRESHENER = "AIR_FRESHENER"

    # Indicates a device that improves the quality of air in interior spaces.
    AIR_PURIFIER = "AIR_PURIFIER"

    # Indicates a smart device in an automobile, such as a dash camera.
    AUTO_ACCESSORY = "AUTO_ACCESSORY"

    # Indicates a security device with video or photo functionality.
    CAMERA = "CAMERA"

    # Indicates a religious holiday decoration that often contains lights.
    CHRISTMAS_TREE = "CHRISTMAS_TREE"

    # Indicates a device that makes coffee.
    COFFEE_MAKER = "COFFEE_MAKER"

    # Indicates a non-mobile computer, such as a desktop computer.
    COMPUTER = "COMPUTER"

    # Indicates an endpoint that detects and reports contact.
    CONTACT_SENSOR = "CONTACT_SENSOR"

    # Indicates a door.
    DOOR = "DOOR"

    # Indicates a doorbell.
    DOORBELL = "DOORBELL"

    # Indicates a window covering on the outside of a structure.
    EXTERIOR_BLIND = "EXTERIOR_BLIND"

    # Indicates a fan.
    FAN = "FAN"

    # Indicates a game console, such as Microsoft Xbox or Nintendo Switch
    GAME_CONSOLE = "GAME_CONSOLE"

    # Indicates a garage door.
    # Garage doors must implement the ModeController interface to open and close the door.
    GARAGE_DOOR = "GARAGE_DOOR"

    # Indicates a wearable device that transmits audio directly into the ear.
    HEADPHONES = "HEADPHONES"

    # Indicates a smart-home hub.
    HUB = "HUB"

    # Indicates a window covering on the inside of a structure.
    INTERIOR_BLIND = "INTERIOR_BLIND"

    # Indicates a laptop or other mobile computer.
    LAPTOP = "LAPTOP"

    # Indicates light sources or fixtures.
    LIGHT = "LIGHT"

    # Indicates a microwave oven.
    MICROWAVE = "MICROWAVE"

    # Indicates a mobile phone.
    MOBILE_PHONE = "MOBILE_PHONE"

    # Indicates an endpoint that detects and reports motion.
    MOTION_SENSOR = "MOTION_SENSOR"

    # Indicates a network-connected music system.
    MUSIC_SYSTEM = "MUSIC_SYSTEM"

    # Indicates a network router.
    NETWORK_HARDWARE = "NETWORK_HARDWARE"

    # An endpoint that cannot be described in on of the other categories.
    OTHER = "OTHER"

    # Indicates an oven cooking appliance.
    OVEN = "OVEN"

    # Indicates a non-mobile phone, such as landline or an IP phone.
    PHONE = "PHONE"

    # Indicates a device that prints.
    PRINTER = "PRINTER"

    # Indicates a network router.
    ROUTER = "ROUTER"

    # Describes a combination of devices set to a specific state, when the
    # order of the state change is not important. For example a bedtime scene
    # might include turning off lights and lowering the thermostat, but the
    # order is unimportant.    Applies to Scenes
    SCENE_TRIGGER = "SCENE_TRIGGER"

    # Indicates a projector screen.
    SCREEN = "SCREEN"

    # Indicates a security panel.
    SECURITY_PANEL = "SECURITY_PANEL"

    # Indicates a security system.
    SECURITY_SYSTEM = "SECURITY_SYSTEM"

    # Indicates an electric cooking device that sits on a countertop, cooks at low temperatures,
    # and is often shaped like a cooking pot.
    SLOW_COOKER = "SLOW_COOKER"

    # Indicates an endpoint that locks.
    SMARTLOCK = "SMARTLOCK"

    # Indicates modules that are plugged into an existing electrical outlet.
    # Can control a variety of devices.
    SMARTPLUG = "SMARTPLUG"

    # Indicates the endpoint is a speaker or speaker system.
    SPEAKER = "SPEAKER"

    # Indicates a streaming device such as Apple TV, Chromecast, or Roku.
    STREAMING_DEVICE = "STREAMING_DEVICE"

    # Indicates in-wall switches wired to the electrical system.  Can control a
    # variety of devices.
    SWITCH = "SWITCH"

    # Indicates a tablet computer.
    TABLET = "TABLET"

    # Indicates endpoints that report the temperature only.
    TEMPERATURE_SENSOR = "TEMPERATURE_SENSOR"

    # Indicates endpoints that control temperature, stand-alone air
    # conditioners, or heaters with direct temperature control.
    THERMOSTAT = "THERMOSTAT"

    # Indicates the endpoint is a television.
    TV = "TV"

    # Indicates a vacuum cleaner.
    VACUUM_CLEANER = "VACUUM_CLEANER"

    # Indicates a network-connected wearable device, such as an Apple Watch, Fitbit, or Samsung Gear.
    WEARABLE = "WEARABLE"


def generate_alexa_id(entity_id: str) -> str:
    """Return the alexa ID for an entity ID."""
    return entity_id.replace(".", "#").translate(TRANSLATION_TABLE)


class AlexaEntity:
    """An adaptation of an entity, expressed in Alexa's terms.

    The API handlers should manipulate entities only through this interface.
    """

    def __init__(
        self, hass: HomeAssistant, config: AbstractConfig, entity: State
    ) -> None:
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
        return generate_alexa_id(self.entity.entity_id)

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

    def get_interface(self, capability) -> AlexaCapability:
        """Return the given AlexaInterface.

        Raises _UnsupportedInterface.
        """

    def interfaces(self) -> list[AlexaCapability]:
        """Return a list of supported interfaces.

        Used for discovery. The list should contain AlexaInterface instances.
        If the list is empty, this entity will not be discovered.
        """
        raise NotImplementedError

    def serialize_properties(self):
        """Yield each supported property in API format."""
        for interface in self.interfaces():
            if not interface.properties_proactively_reported():
                continue

            yield from interface.serialize_properties()

    def serialize_discovery(self):
        """Serialize the entity for discovery."""
        result = {
            "displayCategories": self.display_categories(),
            "cookie": {},
            "endpointId": self.alexa_id(),
            "friendlyName": self.friendly_name(),
            "description": self.description(),
            "manufacturerName": "Home Assistant",
            "additionalAttributes": {
                "manufacturer": "Home Assistant",
                "model": self.entity.domain,
                "softwareVersion": __version__,
                "customIdentifier": f"{self.config.user_identifier()}-{self.entity_id}",
            },
        }

        locale = self.config.locale
        capabilities = []

        for i in self.interfaces():
            if locale not in i.supported_locales:
                continue

            try:
                capabilities.append(i.serialize_discovery())
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Error serializing %s discovery for %s", i.name(), self.entity
                )

        result["capabilities"] = capabilities

        return result


@callback
def async_get_entities(hass, config) -> list[AlexaEntity]:
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
class GenericCapabilities(AlexaEntity):
    """A generic, on/off device.

    The choice of last resort.
    """

    def default_display_categories(self):
        """Return the display categories for this entity."""
        if self.entity.domain == automation.DOMAIN:
            return [DisplayCategory.ACTIVITY_TRIGGER]

        return [DisplayCategory.OTHER]

    def interfaces(self):
        """Yield the supported interfaces."""
        return [
            AlexaPowerController(self.entity),
            AlexaEndpointHealth(self.hass, self.entity),
            Alexa(self.hass),
        ]


@ENTITY_ADAPTERS.register(input_boolean.DOMAIN)
@ENTITY_ADAPTERS.register(switch.DOMAIN)
class SwitchCapabilities(AlexaEntity):
    """Class to represent Switch capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        if self.entity.domain == input_boolean.DOMAIN:
            return [DisplayCategory.OTHER]

        device_class = self.entity.attributes.get(ATTR_DEVICE_CLASS)
        if device_class == switch.SwitchDeviceClass.OUTLET:
            return [DisplayCategory.SMARTPLUG]

        return [DisplayCategory.SWITCH]

    def interfaces(self):
        """Yield the supported interfaces."""
        return [
            AlexaPowerController(self.entity),
            AlexaContactSensor(self.hass, self.entity),
            AlexaEndpointHealth(self.hass, self.entity),
            Alexa(self.hass),
        ]


@ENTITY_ADAPTERS.register(button.DOMAIN)
@ENTITY_ADAPTERS.register(input_button.DOMAIN)
class ButtonCapabilities(AlexaEntity):
    """Class to represent Button capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.ACTIVITY_TRIGGER]

    def interfaces(self):
        """Yield the supported interfaces."""
        return [
            AlexaSceneController(self.entity, supports_deactivation=False),
            AlexaEventDetectionSensor(self.hass, self.entity),
            AlexaEndpointHealth(self.hass, self.entity),
            Alexa(self.hass),
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
        yield Alexa(self.hass)


@ENTITY_ADAPTERS.register(cover.DOMAIN)
class CoverCapabilities(AlexaEntity):
    """Class to represent Cover capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        device_class = self.entity.attributes.get(ATTR_DEVICE_CLASS)
        if device_class in (cover.CoverDeviceClass.GARAGE, cover.CoverDeviceClass.GATE):
            return [DisplayCategory.GARAGE_DOOR]
        if device_class == cover.CoverDeviceClass.DOOR:
            return [DisplayCategory.DOOR]
        if device_class in (
            cover.CoverDeviceClass.BLIND,
            cover.CoverDeviceClass.SHADE,
            cover.CoverDeviceClass.CURTAIN,
        ):
            return [DisplayCategory.INTERIOR_BLIND]
        if device_class in (
            cover.CoverDeviceClass.WINDOW,
            cover.CoverDeviceClass.AWNING,
            cover.CoverDeviceClass.SHUTTER,
        ):
            return [DisplayCategory.EXTERIOR_BLIND]

        return [DisplayCategory.OTHER]

    def interfaces(self):
        """Yield the supported interfaces."""
        device_class = self.entity.attributes.get(ATTR_DEVICE_CLASS)
        if device_class not in (
            cover.CoverDeviceClass.GARAGE,
            cover.CoverDeviceClass.GATE,
        ):
            yield AlexaPowerController(self.entity)

        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & cover.CoverEntityFeature.SET_POSITION:
            yield AlexaRangeController(
                self.entity, instance=f"{cover.DOMAIN}.{cover.ATTR_POSITION}"
            )
        elif supported & (
            cover.CoverEntityFeature.CLOSE | cover.CoverEntityFeature.OPEN
        ):
            yield AlexaModeController(
                self.entity, instance=f"{cover.DOMAIN}.{cover.ATTR_POSITION}"
            )
        if supported & cover.CoverEntityFeature.SET_TILT_POSITION:
            yield AlexaRangeController(self.entity, instance=f"{cover.DOMAIN}.tilt")
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.hass)


@ENTITY_ADAPTERS.register(light.DOMAIN)
class LightCapabilities(AlexaEntity):
    """Class to represent Light capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.LIGHT]

    def interfaces(self):
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)

        color_modes = self.entity.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES)
        if light.brightness_supported(color_modes):
            yield AlexaBrightnessController(self.entity)
        if light.color_supported(color_modes):
            yield AlexaColorController(self.entity)
        if light.color_temp_supported(color_modes):
            yield AlexaColorTemperatureController(self.entity)

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.hass)


@ENTITY_ADAPTERS.register(fan.DOMAIN)
class FanCapabilities(AlexaEntity):
    """Class to represent Fan capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.FAN]

    def interfaces(self):
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)
        force_range_controller = True
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & fan.FanEntityFeature.OSCILLATE:
            yield AlexaToggleController(
                self.entity, instance=f"{fan.DOMAIN}.{fan.ATTR_OSCILLATING}"
            )
            force_range_controller = False
        if supported & fan.FanEntityFeature.PRESET_MODE:
            yield AlexaModeController(
                self.entity, instance=f"{fan.DOMAIN}.{fan.ATTR_PRESET_MODE}"
            )
            force_range_controller = False
        if supported & fan.FanEntityFeature.DIRECTION:
            yield AlexaModeController(
                self.entity, instance=f"{fan.DOMAIN}.{fan.ATTR_DIRECTION}"
            )
            force_range_controller = False

        # AlexaRangeController controls the Fan Speed Percentage.
        # For fans which only support on/off, no controller is added. This makes the
        # fan impossible to turn on or off through Alexa, most likely due to a bug in Alexa.
        # As a workaround, we add a range controller which can only be set to 0% or 100%.
        if force_range_controller or supported & fan.FanEntityFeature.SET_SPEED:
            yield AlexaRangeController(
                self.entity, instance=f"{fan.DOMAIN}.{fan.ATTR_PERCENTAGE}"
            )

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.hass)


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
            Alexa(self.hass),
        ]


@ENTITY_ADAPTERS.register(media_player.const.DOMAIN)
class MediaPlayerCapabilities(AlexaEntity):
    """Class to represent MediaPlayer capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        device_class = self.entity.attributes.get(ATTR_DEVICE_CLASS)
        if device_class == media_player.MediaPlayerDeviceClass.SPEAKER:
            return [DisplayCategory.SPEAKER]

        return [DisplayCategory.TV]

    def interfaces(self):
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)

        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & media_player.MediaPlayerEntityFeature.VOLUME_SET:
            yield AlexaSpeaker(self.entity)
        elif supported & media_player.MediaPlayerEntityFeature.VOLUME_STEP:
            yield AlexaStepSpeaker(self.entity)

        playback_features = (
            media_player.MediaPlayerEntityFeature.PLAY
            | media_player.MediaPlayerEntityFeature.PAUSE
            | media_player.MediaPlayerEntityFeature.STOP
            | media_player.MediaPlayerEntityFeature.NEXT_TRACK
            | media_player.MediaPlayerEntityFeature.PREVIOUS_TRACK
        )
        if supported & playback_features:
            yield AlexaPlaybackController(self.entity)
            yield AlexaPlaybackStateReporter(self.entity)

        if supported & media_player.MediaPlayerEntityFeature.SEEK:
            yield AlexaSeekController(self.entity)

        if supported & media_player.MediaPlayerEntityFeature.SELECT_SOURCE:
            inputs = AlexaInputController.get_valid_inputs(
                self.entity.attributes.get(
                    media_player.const.ATTR_INPUT_SOURCE_LIST, []
                )
            )
            if len(inputs) > 0:
                yield AlexaInputController(self.entity)

        if supported & media_player.MediaPlayerEntityFeature.PLAY_MEDIA:
            yield AlexaChannelController(self.entity)

        # AlexaEqualizerController is disabled for denonavr
        # since it blocks alexa from discovering any devices.
        domain = entity_sources(self.hass).get(self.entity_id, {}).get("domain")
        if (
            supported & media_player.MediaPlayerEntityFeature.SELECT_SOUND_MODE
            and domain != "denonavr"
        ):
            inputs = AlexaEqualizerController.get_valid_inputs(
                self.entity.attributes.get(media_player.const.ATTR_SOUND_MODE_LIST, [])
            )
            if len(inputs) > 0:
                yield AlexaEqualizerController(self.entity)

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.hass)


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
        return [
            AlexaSceneController(self.entity, supports_deactivation=False),
            Alexa(self.hass),
        ]


@ENTITY_ADAPTERS.register(script.DOMAIN)
class ScriptCapabilities(AlexaEntity):
    """Class to represent Script capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.ACTIVITY_TRIGGER]

    def interfaces(self):
        """Yield the supported interfaces."""
        return [
            AlexaSceneController(self.entity, supports_deactivation=True),
            Alexa(self.hass),
        ]


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
            yield Alexa(self.hass)


@ENTITY_ADAPTERS.register(binary_sensor.DOMAIN)
class BinarySensorCapabilities(AlexaEntity):
    """Class to represent BinarySensor capabilities."""

    TYPE_CONTACT = "contact"
    TYPE_MOTION = "motion"
    TYPE_PRESENCE = "presence"

    def default_display_categories(self):
        """Return the display categories for this entity."""
        sensor_type = self.get_type()
        if sensor_type is self.TYPE_CONTACT:
            return [DisplayCategory.CONTACT_SENSOR]
        if sensor_type is self.TYPE_MOTION:
            return [DisplayCategory.MOTION_SENSOR]
        if sensor_type is self.TYPE_PRESENCE:
            return [DisplayCategory.CAMERA]

    def interfaces(self):
        """Yield the supported interfaces."""
        sensor_type = self.get_type()
        if sensor_type is self.TYPE_CONTACT:
            yield AlexaContactSensor(self.hass, self.entity)
        elif sensor_type is self.TYPE_MOTION:
            yield AlexaMotionSensor(self.hass, self.entity)
        elif sensor_type is self.TYPE_PRESENCE:
            yield AlexaEventDetectionSensor(self.hass, self.entity)

        # yield additional interfaces based on specified display category in config.
        entity_conf = self.config.entity_config.get(self.entity.entity_id, {})
        if CONF_DISPLAY_CATEGORIES in entity_conf:
            if entity_conf[CONF_DISPLAY_CATEGORIES] == DisplayCategory.DOORBELL:
                yield AlexaDoorbellEventSource(self.entity)
            elif entity_conf[CONF_DISPLAY_CATEGORIES] == DisplayCategory.CONTACT_SENSOR:
                yield AlexaContactSensor(self.hass, self.entity)
            elif entity_conf[CONF_DISPLAY_CATEGORIES] == DisplayCategory.MOTION_SENSOR:
                yield AlexaMotionSensor(self.hass, self.entity)
            elif entity_conf[CONF_DISPLAY_CATEGORIES] == DisplayCategory.CAMERA:
                yield AlexaEventDetectionSensor(self.hass, self.entity)

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.hass)

    def get_type(self):
        """Return the type of binary sensor."""
        attrs = self.entity.attributes
        if attrs.get(ATTR_DEVICE_CLASS) in (
            binary_sensor.BinarySensorDeviceClass.DOOR,
            binary_sensor.BinarySensorDeviceClass.GARAGE_DOOR,
            binary_sensor.BinarySensorDeviceClass.OPENING,
            binary_sensor.BinarySensorDeviceClass.WINDOW,
        ):
            return self.TYPE_CONTACT

        if attrs.get(ATTR_DEVICE_CLASS) == binary_sensor.BinarySensorDeviceClass.MOTION:
            return self.TYPE_MOTION

        if (
            attrs.get(ATTR_DEVICE_CLASS)
            == binary_sensor.BinarySensorDeviceClass.PRESENCE
        ):
            return self.TYPE_PRESENCE


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
            yield Alexa(self.hass)


@ENTITY_ADAPTERS.register(image_processing.DOMAIN)
class ImageProcessingCapabilities(AlexaEntity):
    """Class to represent image_processing capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.CAMERA]

    def interfaces(self):
        """Yield the supported interfaces."""
        yield AlexaEventDetectionSensor(self.hass, self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.hass)


@ENTITY_ADAPTERS.register(input_number.DOMAIN)
class InputNumberCapabilities(AlexaEntity):
    """Class to represent input_number capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.OTHER]

    def interfaces(self):
        """Yield the supported interfaces."""

        yield AlexaRangeController(
            self.entity, instance=f"{input_number.DOMAIN}.{input_number.ATTR_VALUE}"
        )
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.hass)


@ENTITY_ADAPTERS.register(timer.DOMAIN)
class TimerCapabilities(AlexaEntity):
    """Class to represent Timer capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.OTHER]

    def interfaces(self):
        """Yield the supported interfaces."""
        yield AlexaTimeHoldController(self.entity, allow_remote_resume=True)
        yield AlexaPowerController(self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(vacuum.DOMAIN)
class VacuumCapabilities(AlexaEntity):
    """Class to represent vacuum capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.VACUUM_CLEANER]

    def interfaces(self):
        """Yield the supported interfaces."""
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if (
            (supported & vacuum.VacuumEntityFeature.TURN_ON)
            or (supported & vacuum.VacuumEntityFeature.START)
        ) and (
            (supported & vacuum.VacuumEntityFeature.TURN_OFF)
            or (supported & vacuum.VacuumEntityFeature.RETURN_HOME)
        ):
            yield AlexaPowerController(self.entity)

        if supported & vacuum.VacuumEntityFeature.FAN_SPEED:
            yield AlexaRangeController(
                self.entity, instance=f"{vacuum.DOMAIN}.{vacuum.ATTR_FAN_SPEED}"
            )

        if supported & vacuum.VacuumEntityFeature.PAUSE:
            support_resume = bool(supported & vacuum.VacuumEntityFeature.START)
            yield AlexaTimeHoldController(
                self.entity, allow_remote_resume=support_resume
            )

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.hass)


@ENTITY_ADAPTERS.register(camera.DOMAIN)
class CameraCapabilities(AlexaEntity):
    """Class to represent Camera capabilities."""

    def default_display_categories(self):
        """Return the display categories for this entity."""
        return [DisplayCategory.CAMERA]

    def interfaces(self):
        """Yield the supported interfaces."""
        if self._check_requirements():
            supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            if supported & camera.CameraEntityFeature.STREAM:
                yield AlexaCameraStreamController(self.entity)

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.hass)

    def _check_requirements(self):
        """Check the hass URL for HTTPS scheme."""
        if "stream" not in self.hass.config.components:
            _LOGGER.debug(
                "%s requires stream component for AlexaCameraStreamController",
                self.entity_id,
            )
            return False

        try:
            network.get_url(
                self.hass,
                allow_internal=False,
                allow_ip=False,
                require_ssl=True,
                require_standard_port=True,
            )
        except network.NoURLAvailableError:
            _LOGGER.debug(
                "%s requires HTTPS for AlexaCameraStreamController", self.entity_id
            )
            return False

        return True
