"""Alexa entity adapters."""

from collections.abc import Generator, Iterable
import logging
from typing import TYPE_CHECKING, Any, override

from homeassistant.components import (
    binary_sensor,
    camera,
    climate,
    cover,
    event,
    fan,
    humidifier,
    light,
    media_player,
    remote,
    switch,
    vacuum,
    valve,
    water_heater,
)
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelEntityStateAttribute,
)
from homeassistant.components.alert import DOMAIN as ALERT_DOMAIN
from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntityCapabilityAttribute,
)
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    FanEntityCapabilityAttribute,
)
from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.components.humidifier import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    HumidifierEntityCapabilityAttribute,
)
from homeassistant.components.image_processing import DOMAIN as IMAGE_PROCESSING_DOMAIN
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.components.input_button import DOMAIN as INPUT_BUTTON_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    LightEntityCapabilityAttribute,
)
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerEntityCapabilityAttribute,
)
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.remote import (
    DOMAIN as REMOTE_DOMAIN,
    RemoteEntityStateAttribute,
)
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.timer import DOMAIN as TIMER_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    WaterHeaterCapabilityAttribute,
)
from homeassistant.const import (
    CONF_DESCRIPTION,
    CONF_NAME,
    EntityStateAttribute,
    UnitOfTemperature,
    __version__,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er, intent, network
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

    # Indicates a device that cools the air in interior spaces.
    AIR_CONDITIONER = "AIR_CONDITIONER"

    # Indicates a device that emits pleasant odors and masks unpleasant
    # odors in interior spaces.
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
    # Garage doors must implement the ModeController interface to
    # open and close the door.
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

    # Indicates a decive that support stateless events,
    # such as remote switches and smart buttons.
    REMOTE = "REMOTE"

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

    # Indicates an electric cooking device that sits on a countertop,
    # cooks at low temperatures, and is often shaped like a cooking pot.
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

    # Indicates a water heater.
    WATER_HEATER = "WATER_HEATER"

    # Indicates a network-connected wearable device, such as an Apple Watch,
    # Fitbit, or Samsung Gear.
    WEARABLE = "WEARABLE"


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
    def entity_id(self) -> str:
        """Return the Entity ID."""
        return self.entity.entity_id

    def friendly_name(self) -> str:
        """Return the Alexa API friendly name."""
        name: str | None = self.entity_conf.get(CONF_NAME)
        if name is None:
            entity_entry = er.async_get(self.hass).async_get(self.entity_id)
            aliases = intent.async_get_entity_aliases(
                self.hass, entity_entry, state=self.entity, allow_empty=False
            )
            name = aliases[0]
        return name.translate(TRANSLATION_TABLE)

    def description(self) -> str:
        """Return the Alexa API description."""
        description = self.entity_conf.get(CONF_DESCRIPTION) or self.entity_id
        return f"{description} via Home Assistant".translate(TRANSLATION_TABLE)

    def alexa_id(self) -> str:
        """Return the Alexa API entity id."""
        return self.config.generate_alexa_id(self.entity.entity_id)

    def display_categories(self) -> list[str] | None:
        """Return a list of display categories."""
        entity_conf = self.config.entity_config.get(self.entity.entity_id, {})
        if CONF_DISPLAY_CATEGORIES in entity_conf:
            return [entity_conf[CONF_DISPLAY_CATEGORIES]]
        return self.default_display_categories()

    def default_display_categories(self) -> list[str] | None:
        """Return a list of default display categories.

        This can be overridden by the user in the Home Assistant configuration.

        See also DisplayCategory.
        """
        raise NotImplementedError

    def interfaces(self) -> Iterable[AlexaCapability]:
        """Return a list of supported interfaces.

        Used for discovery. The list should contain AlexaInterface instances.
        If the list is empty, this entity will not be discovered.
        """
        raise NotImplementedError

    def serialize_properties(self) -> Generator[dict[str, Any]]:
        """Yield each supported property in API format."""
        for interface in self.interfaces():
            if not interface.properties_proactively_reported():
                continue

            yield from interface.serialize_properties()

    def serialize_discovery(self) -> dict[str, Any]:
        """Serialize the entity for discovery."""
        result: dict[str, Any] = {
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
            except Exception:
                _LOGGER.exception(
                    "Error serializing %s discovery for %s", i.name(), self.entity
                )

        result["capabilities"] = capabilities

        return result


@callback
def async_get_entities(
    hass: HomeAssistant, config: AbstractConfig
) -> list[AlexaEntity]:
    """Return all entities that are supported by Alexa."""
    entities: list[AlexaEntity] = []
    for state in hass.states.async_all():
        if state.domain not in ENTITY_ADAPTERS:
            continue

        try:
            alexa_entity = ENTITY_ADAPTERS[state.domain](hass, config, state)
            interfaces = list(alexa_entity.interfaces())
        except Exception:
            _LOGGER.exception("Unable to serialize %s for discovery", state.entity_id)
        else:
            if not interfaces:
                continue
            entities.append(alexa_entity)

    return entities


@ENTITY_ADAPTERS.register(ALERT_DOMAIN)
@ENTITY_ADAPTERS.register(AUTOMATION_DOMAIN)
@ENTITY_ADAPTERS.register(GROUP_DOMAIN)
class GenericCapabilities(AlexaEntity):
    """A generic, on/off device.

    The choice of last resort.
    """

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        if self.entity.domain == AUTOMATION_DOMAIN:
            return [DisplayCategory.ACTIVITY_TRIGGER]

        return [DisplayCategory.OTHER]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(INPUT_BOOLEAN_DOMAIN)
@ENTITY_ADAPTERS.register(SWITCH_DOMAIN)
class SwitchCapabilities(AlexaEntity):
    """Class to represent Switch capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        if self.entity.domain == INPUT_BOOLEAN_DOMAIN:
            return [DisplayCategory.OTHER]

        device_class = self.entity.attributes.get(EntityStateAttribute.DEVICE_CLASS)
        if device_class == switch.SwitchDeviceClass.OUTLET:
            return [DisplayCategory.SMARTPLUG]

        return [DisplayCategory.SWITCH]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)
        yield AlexaContactSensor(self.hass, self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(BUTTON_DOMAIN)
@ENTITY_ADAPTERS.register(INPUT_BUTTON_DOMAIN)
class ButtonCapabilities(AlexaEntity):
    """Class to represent Button capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.ACTIVITY_TRIGGER]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaSceneController(self.entity, supports_deactivation=False)
        yield AlexaEventDetectionSensor(self.hass, self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(CLIMATE_DOMAIN)
@ENTITY_ADAPTERS.register(WATER_HEATER_DOMAIN)
class ClimateCapabilities(AlexaEntity):
    """Class to represent Climate capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        if self.entity.domain == WATER_HEATER_DOMAIN:
            return [DisplayCategory.WATER_HEATER]
        return [DisplayCategory.THERMOSTAT]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        # If we support two modes, one being off, we allow turning on too.
        supported_features = self.entity.attributes.get(
            EntityStateAttribute.SUPPORTED_FEATURES, 0
        )
        if (
            (
                self.entity.domain == CLIMATE_DOMAIN
                and climate.HVACMode.OFF
                in (
                    self.entity.attributes.get(
                        ClimateEntityCapabilityAttribute.HVAC_MODES
                    )
                    or []
                )
            )
            or (
                self.entity.domain == CLIMATE_DOMAIN
                and (
                    supported_features
                    & (
                        climate.ClimateEntityFeature.TURN_ON
                        | climate.ClimateEntityFeature.TURN_OFF
                    )
                )
            )
            or (
                self.entity.domain == WATER_HEATER_DOMAIN
                and (supported_features & water_heater.WaterHeaterEntityFeature.ON_OFF)
            )
        ):
            yield AlexaPowerController(self.entity)

        if self.entity.domain == CLIMATE_DOMAIN or (
            self.entity.domain == WATER_HEATER_DOMAIN
            and (
                supported_features
                & water_heater.WaterHeaterEntityFeature.OPERATION_MODE
            )
        ):
            yield AlexaThermostatController(self.hass, self.entity)
            yield AlexaTemperatureSensor(self.hass, self.entity)
        if (
            self.entity.domain == WATER_HEATER_DOMAIN
            and (
                supported_features
                & water_heater.WaterHeaterEntityFeature.OPERATION_MODE
            )
            and self.entity.attributes.get(
                WaterHeaterCapabilityAttribute.OPERATION_LIST
            )
        ):
            yield AlexaModeController(
                self.entity,
                instance=f"{WATER_HEATER_DOMAIN}.{water_heater.ATTR_OPERATION_MODE}",
            )
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(COVER_DOMAIN)
class CoverCapabilities(AlexaEntity):
    """Class to represent Cover capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        device_class = self.entity.attributes.get(EntityStateAttribute.DEVICE_CLASS)
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

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        device_class = self.entity.attributes.get(EntityStateAttribute.DEVICE_CLASS)
        if device_class not in (
            cover.CoverDeviceClass.GARAGE,
            cover.CoverDeviceClass.GATE,
        ):
            yield AlexaPowerController(self.entity)

        supported = self.entity.attributes.get(
            EntityStateAttribute.SUPPORTED_FEATURES, 0
        )
        if supported & cover.CoverEntityFeature.SET_POSITION:
            yield AlexaRangeController(
                self.entity, instance=f"{COVER_DOMAIN}.{cover.ATTR_POSITION}"
            )
        elif supported & (
            cover.CoverEntityFeature.CLOSE | cover.CoverEntityFeature.OPEN
        ):
            yield AlexaModeController(
                self.entity, instance=f"{COVER_DOMAIN}.{cover.ATTR_POSITION}"
            )
        if supported & cover.CoverEntityFeature.SET_TILT_POSITION:
            yield AlexaRangeController(self.entity, instance=f"{COVER_DOMAIN}.tilt")
        if supported & (
            cover.CoverEntityFeature.STOP | cover.CoverEntityFeature.STOP_TILT
        ):
            yield AlexaPlaybackController(self.entity, instance=f"{COVER_DOMAIN}.stop")
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(EVENT_DOMAIN)
class EventCapabilities(AlexaEntity):
    """Class to represent doorbel event capabilities."""

    @override
    def default_display_categories(self) -> list[str] | None:
        """Return the display categories for this entity."""
        attrs = self.entity.attributes
        device_class: event.EventDeviceClass | None = attrs.get(
            EntityStateAttribute.DEVICE_CLASS
        )
        if device_class == event.EventDeviceClass.DOORBELL:
            return [DisplayCategory.DOORBELL]
        return None

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        if self.default_display_categories() is not None:
            yield AlexaDoorbellEventSource(self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(LIGHT_DOMAIN)
class LightCapabilities(AlexaEntity):
    """Class to represent Light capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.LIGHT]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)

        color_modes = self.entity.attributes.get(
            LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES
        )
        if light.brightness_supported(color_modes):
            yield AlexaBrightnessController(self.entity)
        if light.color_supported(color_modes):
            yield AlexaColorController(self.entity)
        if light.color_temp_supported(color_modes):
            yield AlexaColorTemperatureController(self.entity)

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(FAN_DOMAIN)
class FanCapabilities(AlexaEntity):
    """Class to represent Fan capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.FAN]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)
        force_range_controller = True
        supported = self.entity.attributes.get(
            EntityStateAttribute.SUPPORTED_FEATURES, 0
        )
        if supported & fan.FanEntityFeature.OSCILLATE:
            yield AlexaToggleController(
                self.entity, instance=f"{FAN_DOMAIN}.{fan.ATTR_OSCILLATING}"
            )
            force_range_controller = False
        if supported & fan.FanEntityFeature.PRESET_MODE and self.entity.attributes.get(
            FanEntityCapabilityAttribute.PRESET_MODES
        ):
            yield AlexaModeController(
                self.entity, instance=f"{FAN_DOMAIN}.{fan.ATTR_PRESET_MODE}"
            )
            force_range_controller = False
        if supported & fan.FanEntityFeature.DIRECTION:
            yield AlexaModeController(
                self.entity, instance=f"{FAN_DOMAIN}.{fan.ATTR_DIRECTION}"
            )
            force_range_controller = False

        # AlexaRangeController controls the Fan Speed Percentage.
        # For fans which only support on/off, no controller is added. This makes
        # the fan impossible to turn on or off through Alexa, most likely due
        # to a bug in Alexa. As a workaround, we add a range controller which
        # can only be set to 0% or 100%.
        if force_range_controller or supported & fan.FanEntityFeature.SET_SPEED:
            yield AlexaRangeController(
                self.entity, instance=f"{FAN_DOMAIN}.{fan.ATTR_PERCENTAGE}"
            )

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(REMOTE_DOMAIN)
class RemoteCapabilities(AlexaEntity):
    """Class to represent Remote capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.REMOTE]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)
        supported = self.entity.attributes.get(
            EntityStateAttribute.SUPPORTED_FEATURES, 0
        )
        activities = (
            self.entity.attributes.get(RemoteEntityStateAttribute.ACTIVITY_LIST) or []
        )
        if (
            activities
            and (supported & remote.RemoteEntityFeature.ACTIVITY)
            and self.entity.attributes.get(RemoteEntityStateAttribute.ACTIVITY_LIST)
        ):
            yield AlexaModeController(
                self.entity, instance=f"{REMOTE_DOMAIN}.{remote.ATTR_ACTIVITY}"
            )
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(HUMIDIFIER_DOMAIN)
class HumidifierCapabilities(AlexaEntity):
    """Class to represent Humidifier capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.OTHER]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)
        supported = self.entity.attributes.get(
            EntityStateAttribute.SUPPORTED_FEATURES, 0
        )
        if (
            supported & humidifier.HumidifierEntityFeature.MODES
        ) and self.entity.attributes.get(
            HumidifierEntityCapabilityAttribute.AVAILABLE_MODES
        ):
            yield AlexaModeController(
                self.entity, instance=f"{HUMIDIFIER_DOMAIN}.{humidifier.ATTR_MODE}"
            )
        yield AlexaRangeController(
            self.entity, instance=f"{HUMIDIFIER_DOMAIN}.{humidifier.ATTR_HUMIDITY}"
        )

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(LOCK_DOMAIN)
class LockCapabilities(AlexaEntity):
    """Class to represent Lock capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.SMARTLOCK]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaLockController(self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(MEDIA_PLAYER_DOMAIN)
class MediaPlayerCapabilities(AlexaEntity):
    """Class to represent MediaPlayer capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        device_class = self.entity.attributes.get(EntityStateAttribute.DEVICE_CLASS)
        if device_class == media_player.MediaPlayerDeviceClass.SPEAKER:
            return [DisplayCategory.SPEAKER]

        return [DisplayCategory.TV]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaPowerController(self.entity)

        supported = self.entity.attributes.get(
            EntityStateAttribute.SUPPORTED_FEATURES, 0
        )
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
                    MediaPlayerEntityCapabilityAttribute.INPUT_SOURCE_LIST, []
                )
            )
            if len(inputs) > 0:
                yield AlexaInputController(self.entity)

        if supported & media_player.MediaPlayerEntityFeature.PLAY_MEDIA:
            yield AlexaChannelController(self.entity)

        # AlexaEqualizerController is disabled for denonavr
        # since it blocks alexa from discovering any devices.
        entity_info = entity_sources(self.hass).get(self.entity_id)
        domain = entity_info["domain"] if entity_info else None
        if (
            supported & media_player.MediaPlayerEntityFeature.SELECT_SOUND_MODE
            and domain != "denonavr"
        ):
            inputs = AlexaEqualizerController.get_valid_inputs(
                self.entity.attributes.get(
                    MediaPlayerEntityCapabilityAttribute.SOUND_MODE_LIST
                )
                or []
            )
            if len(inputs) > 0:
                yield AlexaEqualizerController(self.entity)

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(SCENE_DOMAIN)
class SceneCapabilities(AlexaEntity):
    """Class to represent Scene capabilities."""

    @override
    def description(self) -> str:
        """Return the Alexa API description."""
        description = AlexaEntity.description(self)
        if "scene" not in description.casefold():
            return f"{description} (Scene)"
        return description

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.SCENE_TRIGGER]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaSceneController(self.entity, supports_deactivation=False)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(SCRIPT_DOMAIN)
class ScriptCapabilities(AlexaEntity):
    """Class to represent Script capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.ACTIVITY_TRIGGER]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaSceneController(self.entity, supports_deactivation=True)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(SENSOR_DOMAIN)
class SensorCapabilities(AlexaEntity):
    """Class to represent Sensor capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        # although there are other kinds of sensors, all but temperature
        # sensors are currently ignored.
        return [DisplayCategory.TEMPERATURE_SENSOR]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        attrs = self.entity.attributes
        if attrs.get(EntityStateAttribute.UNIT_OF_MEASUREMENT) in {
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
        }:
            yield AlexaTemperatureSensor(self.hass, self.entity)
            yield AlexaEndpointHealth(self.hass, self.entity)
            yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(BINARY_SENSOR_DOMAIN)
class BinarySensorCapabilities(AlexaEntity):
    """Class to represent BinarySensor capabilities."""

    TYPE_CONTACT = "contact"
    TYPE_MOTION = "motion"
    TYPE_PRESENCE = "presence"

    @override
    def default_display_categories(self) -> list[str] | None:
        """Return the display categories for this entity."""
        sensor_type = self.get_type()
        if sensor_type is self.TYPE_CONTACT:
            return [DisplayCategory.CONTACT_SENSOR]
        if sensor_type is self.TYPE_MOTION:
            return [DisplayCategory.MOTION_SENSOR]
        if sensor_type is self.TYPE_PRESENCE:
            return [DisplayCategory.CAMERA]
        return None

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
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
        yield Alexa(self.entity)

    def get_type(self) -> str | None:
        """Return the type of binary sensor."""
        attrs = self.entity.attributes
        if attrs.get(EntityStateAttribute.DEVICE_CLASS) in (
            binary_sensor.BinarySensorDeviceClass.DOOR,
            binary_sensor.BinarySensorDeviceClass.GARAGE_DOOR,
            binary_sensor.BinarySensorDeviceClass.OPENING,
            binary_sensor.BinarySensorDeviceClass.WINDOW,
        ):
            return self.TYPE_CONTACT

        if (
            attrs.get(EntityStateAttribute.DEVICE_CLASS)
            == binary_sensor.BinarySensorDeviceClass.MOTION
        ):
            return self.TYPE_MOTION

        if (
            attrs.get(EntityStateAttribute.DEVICE_CLASS)
            == binary_sensor.BinarySensorDeviceClass.PRESENCE
        ):
            return self.TYPE_PRESENCE

        return None


@ENTITY_ADAPTERS.register(ALARM_CONTROL_PANEL_DOMAIN)
class AlarmControlPanelCapabilities(AlexaEntity):
    """Class to represent Alarm capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.SECURITY_PANEL]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        if not self.entity.attributes.get(
            AlarmControlPanelEntityStateAttribute.CODE_ARM_REQUIRED
        ):
            yield AlexaSecurityPanelController(self.hass, self.entity)
            yield AlexaEndpointHealth(self.hass, self.entity)
            yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(IMAGE_PROCESSING_DOMAIN)
class ImageProcessingCapabilities(AlexaEntity):
    """Class to represent image_processing capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.CAMERA]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaEventDetectionSensor(self.hass, self.entity)
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(INPUT_NUMBER_DOMAIN)
@ENTITY_ADAPTERS.register(NUMBER_DOMAIN)
class InputNumberCapabilities(AlexaEntity):
    """Class to represent number and input_number capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.OTHER]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        domain = self.entity.domain
        yield AlexaRangeController(self.entity, instance=f"{domain}.value")
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(TIMER_DOMAIN)
class TimerCapabilities(AlexaEntity):
    """Class to represent Timer capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.OTHER]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        yield AlexaTimeHoldController(self.entity, allow_remote_resume=True)
        yield AlexaPowerController(self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(VACUUM_DOMAIN)
class VacuumCapabilities(AlexaEntity):
    """Class to represent vacuum capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.VACUUM_CLEANER]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        supported = self.entity.attributes.get(
            EntityStateAttribute.SUPPORTED_FEATURES, 0
        )
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
                self.entity, instance=f"{VACUUM_DOMAIN}.{vacuum.ATTR_FAN_SPEED}"
            )

        if supported & vacuum.VacuumEntityFeature.PAUSE:
            support_resume = bool(supported & vacuum.VacuumEntityFeature.START)
            yield AlexaTimeHoldController(
                self.entity, allow_remote_resume=support_resume
            )

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(VALVE_DOMAIN)
class ValveCapabilities(AlexaEntity):
    """Class to represent Valve capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.OTHER]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        supported = self.entity.attributes.get(
            EntityStateAttribute.SUPPORTED_FEATURES, 0
        )
        if supported & valve.ValveEntityFeature.SET_POSITION:
            yield AlexaRangeController(
                self.entity, instance=f"{VALVE_DOMAIN}.{valve.ATTR_POSITION}"
            )
        elif supported & (
            valve.ValveEntityFeature.CLOSE | valve.ValveEntityFeature.OPEN
        ):
            yield AlexaModeController(self.entity, instance=f"{VALVE_DOMAIN}.state")
        if supported & valve.ValveEntityFeature.STOP:
            yield AlexaToggleController(self.entity, instance=f"{VALVE_DOMAIN}.stop")
        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)


@ENTITY_ADAPTERS.register(CAMERA_DOMAIN)
class CameraCapabilities(AlexaEntity):
    """Class to represent Camera capabilities."""

    @override
    def default_display_categories(self) -> list[str]:
        """Return the display categories for this entity."""
        return [DisplayCategory.CAMERA]

    @override
    def interfaces(self) -> Generator[AlexaCapability]:
        """Yield the supported interfaces."""
        if self._check_requirements():
            supported = self.entity.attributes.get(
                EntityStateAttribute.SUPPORTED_FEATURES, 0
            )
            if supported & camera.CameraEntityFeature.STREAM:
                yield AlexaCameraStreamController(self.entity)

        yield AlexaEndpointHealth(self.hass, self.entity)
        yield Alexa(self.entity)

    def _check_requirements(self) -> bool:
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
