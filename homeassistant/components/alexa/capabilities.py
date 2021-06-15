"""Alexa capabilities."""
from __future__ import annotations

import logging

from homeassistant.components import (
    cover,
    fan,
    image_processing,
    input_number,
    light,
    timer,
    vacuum,
)
from homeassistant.components.alarm_control_panel import ATTR_CODE_FORMAT, FORMAT_NUMBER
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
import homeassistant.components.climate.const as climate
import homeassistant.components.media_player.const as media_player
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_IDLE,
    STATE_LOCKED,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
)
from homeassistant.core import State
import homeassistant.util.color as color_util
import homeassistant.util.dt as dt_util

from .const import (
    API_TEMP_UNITS,
    API_THERMOSTAT_MODES,
    API_THERMOSTAT_PRESETS,
    DATE_FORMAT,
    Inputs,
)
from .errors import UnsupportedProperty
from .resources import (
    AlexaCapabilityResource,
    AlexaGlobalCatalog,
    AlexaModeResource,
    AlexaPresetResource,
    AlexaSemantics,
)

_LOGGER = logging.getLogger(__name__)


class AlexaCapability:
    """Base class for Alexa capability interfaces.

    The Smart Home Skills API defines a number of "capability interfaces",
    roughly analogous to domains in Home Assistant. The supported interfaces
    describe what actions can be performed on a particular device.

    https://developer.amazon.com/docs/device-apis/message-guide.html
    """

    supported_locales = {"en-US"}

    def __init__(self, entity: State, instance: str | None = None) -> None:
        """Initialize an Alexa capability."""
        self.entity = entity
        self.instance = instance

    def name(self) -> str:
        """Return the Alexa API name of this interface."""
        raise NotImplementedError

    @staticmethod
    def properties_supported() -> list[dict]:
        """Return what properties this entity supports."""
        return []

    @staticmethod
    def properties_proactively_reported() -> bool:
        """Return True if properties asynchronously reported."""
        return False

    @staticmethod
    def properties_retrievable() -> bool:
        """Return True if properties can be retrieved."""
        return False

    @staticmethod
    def properties_non_controllable() -> bool:
        """Return True if non controllable."""
        return None

    @staticmethod
    def get_property(name):
        """Read and return a property.

        Return value should be a dict, or raise UnsupportedProperty.

        Properties can also have a timeOfSample and uncertaintyInMilliseconds,
        but returning those metadata is not yet implemented.
        """
        raise UnsupportedProperty(name)

    @staticmethod
    def supports_deactivation():
        """Applicable only to scenes."""
        return None

    @staticmethod
    def capability_proactively_reported():
        """Return True if the capability is proactively reported.

        Set properties_proactively_reported() for proactively reported properties.
        Applicable to DoorbellEventSource.
        """
        return None

    @staticmethod
    def capability_resources():
        """Return the capability object.

        Applicable to ToggleController, RangeController, and ModeController interfaces.
        """
        return []

    @staticmethod
    def configuration():
        """Return the configuration object.

        Applicable to the ThermostatController, SecurityControlPanel, ModeController, RangeController,
        and EventDetectionSensor.
        """
        return []

    @staticmethod
    def configurations():
        """Return the configurations object.

        The plural configurations object is different that the singular configuration object.
        Applicable to EqualizerController interface.
        """
        return []

    @staticmethod
    def inputs():
        """Applicable only to media players."""
        return []

    @staticmethod
    def semantics():
        """Return the semantics object.

        Applicable to ToggleController, RangeController, and ModeController interfaces.
        """
        return []

    @staticmethod
    def supported_operations():
        """Return the supportedOperations object."""
        return []

    @staticmethod
    def camera_stream_configurations():
        """Applicable only to CameraStreamController."""
        return None

    def serialize_discovery(self):
        """Serialize according to the Discovery API."""
        result = {"type": "AlexaInterface", "interface": self.name(), "version": "3"}

        instance = self.instance
        if instance is not None:
            result["instance"] = instance

        properties_supported = self.properties_supported()
        if properties_supported:
            result["properties"] = {
                "supported": self.properties_supported(),
                "proactivelyReported": self.properties_proactively_reported(),
                "retrievable": self.properties_retrievable(),
            }

        proactively_reported = self.capability_proactively_reported()
        if proactively_reported is not None:
            result["proactivelyReported"] = proactively_reported

        non_controllable = self.properties_non_controllable()
        if non_controllable is not None:
            result["properties"]["nonControllable"] = non_controllable

        supports_deactivation = self.supports_deactivation()
        if supports_deactivation is not None:
            result["supportsDeactivation"] = supports_deactivation

        capability_resources = self.capability_resources()
        if capability_resources:
            result["capabilityResources"] = capability_resources

        configuration = self.configuration()
        if configuration:
            result["configuration"] = configuration

        # The plural configurations object is different than the singular configuration object above.
        configurations = self.configurations()
        if configurations:
            result["configurations"] = configurations

        semantics = self.semantics()
        if semantics:
            result["semantics"] = semantics

        supported_operations = self.supported_operations()
        if supported_operations:
            result["supportedOperations"] = supported_operations

        inputs = self.inputs()
        if inputs:
            result["inputs"] = inputs

        camera_stream_configurations = self.camera_stream_configurations()
        if camera_stream_configurations:
            result["cameraStreamConfigurations"] = camera_stream_configurations

        return result

    def serialize_properties(self):
        """Return properties serialized for an API response."""
        for prop in self.properties_supported():
            prop_name = prop["name"]
            try:
                prop_value = self.get_property(prop_name)
            except UnsupportedProperty:
                raise
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Unexpected error getting %s.%s property from %s",
                    self.name(),
                    prop_name,
                    self.entity,
                )
                prop_value = None

            if prop_value is None:
                continue

            result = {
                "name": prop_name,
                "namespace": self.name(),
                "value": prop_value,
                "timeOfSample": dt_util.utcnow().strftime(DATE_FORMAT),
                "uncertaintyInMilliseconds": 0,
            }
            instance = self.instance
            if instance is not None:
                result["instance"] = instance

            yield result


class Alexa(AlexaCapability):
    """Implements Alexa Interface.

    Although endpoints implement this interface implicitly,
    The API suggests you should explicitly include this interface.

    https://developer.amazon.com/docs/device-apis/alexa-interface.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "fr-CA",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa"


class AlexaEndpointHealth(AlexaCapability):
    """Implements Alexa.EndpointHealth.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#report-state-when-alexa-requests-it
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def __init__(self, hass, entity):
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.EndpointHealth"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "connectivity"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "connectivity":
            raise UnsupportedProperty(name)

        if self.entity.state == STATE_UNAVAILABLE:
            return {"value": "UNREACHABLE"}
        return {"value": "OK"}


class AlexaPowerController(AlexaCapability):
    """Implements Alexa.PowerController.

    https://developer.amazon.com/docs/device-apis/alexa-powercontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.PowerController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "powerState"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "powerState":
            raise UnsupportedProperty(name)

        if self.entity.domain == climate.DOMAIN:
            is_on = self.entity.state != climate.HVAC_MODE_OFF
        elif self.entity.domain == vacuum.DOMAIN:
            is_on = self.entity.state == vacuum.STATE_CLEANING
        elif self.entity.domain == timer.DOMAIN:
            is_on = self.entity.state != STATE_IDLE

        else:
            is_on = self.entity.state != STATE_OFF

        return "ON" if is_on else "OFF"


class AlexaLockController(AlexaCapability):
    """Implements Alexa.LockController.

    https://developer.amazon.com/docs/device-apis/alexa-lockcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.LockController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "lockState"}]

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "lockState":
            raise UnsupportedProperty(name)

        if self.entity.state == STATE_LOCKED:
            return "LOCKED"
        if self.entity.state == STATE_UNLOCKED:
            return "UNLOCKED"
        return "JAMMED"


class AlexaSceneController(AlexaCapability):
    """Implements Alexa.SceneController.

    https://developer.amazon.com/docs/device-apis/alexa-scenecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def __init__(self, entity, supports_deactivation):
        """Initialize the entity."""
        super().__init__(entity)
        self.supports_deactivation = lambda: supports_deactivation

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.SceneController"


class AlexaBrightnessController(AlexaCapability):
    """Implements Alexa.BrightnessController.

    https://developer.amazon.com/docs/device-apis/alexa-brightnesscontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.BrightnessController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "brightness"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "brightness":
            raise UnsupportedProperty(name)
        if "brightness" in self.entity.attributes:
            return round(self.entity.attributes["brightness"] / 255.0 * 100)
        return 0


class AlexaColorController(AlexaCapability):
    """Implements Alexa.ColorController.

    https://developer.amazon.com/docs/device-apis/alexa-colorcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.ColorController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "color"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "color":
            raise UnsupportedProperty(name)

        hue, saturation = self.entity.attributes.get(light.ATTR_HS_COLOR, (0, 0))

        return {
            "hue": hue,
            "saturation": saturation / 100.0,
            "brightness": self.entity.attributes.get(light.ATTR_BRIGHTNESS, 0) / 255.0,
        }


class AlexaColorTemperatureController(AlexaCapability):
    """Implements Alexa.ColorTemperatureController.

    https://developer.amazon.com/docs/device-apis/alexa-colortemperaturecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.ColorTemperatureController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "colorTemperatureInKelvin"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "colorTemperatureInKelvin":
            raise UnsupportedProperty(name)
        if "color_temp" in self.entity.attributes:
            return color_util.color_temperature_mired_to_kelvin(
                self.entity.attributes["color_temp"]
            )
        return None


class AlexaPercentageController(AlexaCapability):
    """Implements Alexa.PercentageController.

    https://developer.amazon.com/docs/device-apis/alexa-percentagecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.PercentageController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "percentage"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "percentage":
            raise UnsupportedProperty(name)

        if self.entity.domain == fan.DOMAIN:
            return self.entity.attributes.get(fan.ATTR_PERCENTAGE) or 0

        if self.entity.domain == cover.DOMAIN:
            return self.entity.attributes.get(cover.ATTR_CURRENT_POSITION, 0)

        return 0


class AlexaSpeaker(AlexaCapability):
    """Implements Alexa.Speaker.

    https://developer.amazon.com/docs/device-apis/alexa-speaker.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "it-IT",
        "ja-JP",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.Speaker"

    def properties_supported(self):
        """Return what properties this entity supports."""
        properties = [{"name": "volume"}]

        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & media_player.SUPPORT_VOLUME_MUTE:
            properties.append({"name": "muted"})

        return properties

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name == "volume":
            current_level = self.entity.attributes.get(
                media_player.ATTR_MEDIA_VOLUME_LEVEL
            )
            if current_level is not None:
                return round(float(current_level) * 100)

        if name == "muted":
            return bool(
                self.entity.attributes.get(media_player.ATTR_MEDIA_VOLUME_MUTED)
            )

        return None


class AlexaStepSpeaker(AlexaCapability):
    """Implements Alexa.StepSpeaker.

    https://developer.amazon.com/docs/device-apis/alexa-stepspeaker.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "it-IT",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.StepSpeaker"


class AlexaPlaybackController(AlexaCapability):
    """Implements Alexa.PlaybackController.

    https://developer.amazon.com/docs/device-apis/alexa-playbackcontroller.html
    """

    supported_locales = {"de-DE", "en-AU", "en-CA", "en-GB", "en-IN", "en-US", "fr-FR"}

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.PlaybackController"

    def supported_operations(self):
        """Return the supportedOperations object.

        Supported Operations: FastForward, Next, Pause, Play, Previous, Rewind, StartOver, Stop
        """
        supported_features = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        operations = {
            media_player.SUPPORT_NEXT_TRACK: "Next",
            media_player.SUPPORT_PAUSE: "Pause",
            media_player.SUPPORT_PLAY: "Play",
            media_player.SUPPORT_PREVIOUS_TRACK: "Previous",
            media_player.SUPPORT_STOP: "Stop",
        }

        return [
            value
            for operation, value in operations.items()
            if operation & supported_features
        ]


class AlexaInputController(AlexaCapability):
    """Implements Alexa.InputController.

    https://developer.amazon.com/docs/device-apis/alexa-inputcontroller.html
    """

    supported_locales = {"de-DE", "en-AU", "en-CA", "en-GB", "en-IN", "en-US"}

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.InputController"

    def inputs(self):
        """Return the list of valid supported inputs."""
        source_list = self.entity.attributes.get(
            media_player.ATTR_INPUT_SOURCE_LIST, []
        )
        return AlexaInputController.get_valid_inputs(source_list)

    @staticmethod
    def get_valid_inputs(source_list):
        """Return list of supported inputs."""
        input_list = []
        for source in source_list:
            formatted_source = (
                source.lower().replace("-", "").replace("_", "").replace(" ", "")
            )
            if formatted_source in Inputs.VALID_SOURCE_NAME_MAP:
                input_list.append(
                    {"name": Inputs.VALID_SOURCE_NAME_MAP[formatted_source]}
                )

        return input_list


class AlexaTemperatureSensor(AlexaCapability):
    """Implements Alexa.TemperatureSensor.

    https://developer.amazon.com/docs/device-apis/alexa-temperaturesensor.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def __init__(self, hass, entity):
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.TemperatureSensor"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "temperature"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "temperature":
            raise UnsupportedProperty(name)

        unit = self.entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        temp = self.entity.state
        if self.entity.domain == climate.DOMAIN:
            unit = self.hass.config.units.temperature_unit
            temp = self.entity.attributes.get(climate.ATTR_CURRENT_TEMPERATURE)

        if temp in (STATE_UNAVAILABLE, STATE_UNKNOWN, None):
            return None

        try:
            temp = float(temp)
        except ValueError:
            _LOGGER.warning("Invalid temp value %s for %s", temp, self.entity.entity_id)
            return None

        return {"value": temp, "scale": API_TEMP_UNITS[unit]}


class AlexaContactSensor(AlexaCapability):
    """Implements Alexa.ContactSensor.

    The Alexa.ContactSensor interface describes the properties and events used
    to report the state of an endpoint that detects contact between two
    surfaces. For example, a contact sensor can report whether a door or window
    is open.

    https://developer.amazon.com/docs/device-apis/alexa-contactsensor.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-IN",
        "en-US",
        "es-ES",
        "it-IT",
        "ja-JP",
    }

    def __init__(self, hass, entity):
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.ContactSensor"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "detectionState"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "detectionState":
            raise UnsupportedProperty(name)

        if self.entity.state == STATE_ON:
            return "DETECTED"
        return "NOT_DETECTED"


class AlexaMotionSensor(AlexaCapability):
    """Implements Alexa.MotionSensor.

    https://developer.amazon.com/docs/device-apis/alexa-motionsensor.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-IN",
        "en-US",
        "es-ES",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, hass, entity):
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.MotionSensor"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "detectionState"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "detectionState":
            raise UnsupportedProperty(name)

        if self.entity.state == STATE_ON:
            return "DETECTED"
        return "NOT_DETECTED"


class AlexaThermostatController(AlexaCapability):
    """Implements Alexa.ThermostatController.

    https://developer.amazon.com/docs/device-apis/alexa-thermostatcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, hass, entity):
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.ThermostatController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        properties = [{"name": "thermostatMode"}]
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & climate.SUPPORT_TARGET_TEMPERATURE:
            properties.append({"name": "targetSetpoint"})
        if supported & climate.SUPPORT_TARGET_TEMPERATURE_RANGE:
            properties.append({"name": "lowerSetpoint"})
            properties.append({"name": "upperSetpoint"})
        return properties

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if self.entity.state == STATE_UNAVAILABLE:
            return None

        if name == "thermostatMode":
            preset = self.entity.attributes.get(climate.ATTR_PRESET_MODE)

            if preset in API_THERMOSTAT_PRESETS:
                mode = API_THERMOSTAT_PRESETS[preset]
            else:
                mode = API_THERMOSTAT_MODES.get(self.entity.state)
                if mode is None:
                    _LOGGER.error(
                        "%s (%s) has unsupported state value '%s'",
                        self.entity.entity_id,
                        type(self.entity),
                        self.entity.state,
                    )
                    raise UnsupportedProperty(name)
            return mode

        unit = self.hass.config.units.temperature_unit
        if name == "targetSetpoint":
            temp = self.entity.attributes.get(ATTR_TEMPERATURE)
        elif name == "lowerSetpoint":
            temp = self.entity.attributes.get(climate.ATTR_TARGET_TEMP_LOW)
        elif name == "upperSetpoint":
            temp = self.entity.attributes.get(climate.ATTR_TARGET_TEMP_HIGH)
        else:
            raise UnsupportedProperty(name)

        if temp is None:
            return None

        try:
            temp = float(temp)
        except ValueError:
            _LOGGER.warning(
                "Invalid temp value %s for %s in %s", temp, name, self.entity.entity_id
            )
            return None

        return {"value": temp, "scale": API_TEMP_UNITS[unit]}

    def configuration(self):
        """Return configuration object.

        Translates climate HVAC_MODES and PRESETS to supported Alexa ThermostatMode Values.
        ThermostatMode Value must be AUTO, COOL, HEAT, ECO, OFF, or CUSTOM.
        """
        supported_modes = []
        hvac_modes = self.entity.attributes.get(climate.ATTR_HVAC_MODES)
        for mode in hvac_modes:
            thermostat_mode = API_THERMOSTAT_MODES.get(mode)
            if thermostat_mode:
                supported_modes.append(thermostat_mode)

        preset_modes = self.entity.attributes.get(climate.ATTR_PRESET_MODES)
        if preset_modes:
            for mode in preset_modes:
                thermostat_mode = API_THERMOSTAT_PRESETS.get(mode)
                if thermostat_mode:
                    supported_modes.append(thermostat_mode)

        # Return False for supportsScheduling until supported with event listener in handler.
        configuration = {"supportsScheduling": False}

        if supported_modes:
            configuration["supportedModes"] = supported_modes

        return configuration


class AlexaPowerLevelController(AlexaCapability):
    """Implements Alexa.PowerLevelController.

    https://developer.amazon.com/docs/device-apis/alexa-powerlevelcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.PowerLevelController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "powerLevel"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "powerLevel":
            raise UnsupportedProperty(name)

        if self.entity.domain == fan.DOMAIN:
            return self.entity.attributes.get(fan.ATTR_PERCENTAGE) or 0


class AlexaSecurityPanelController(AlexaCapability):
    """Implements Alexa.SecurityPanelController.

    https://developer.amazon.com/docs/device-apis/alexa-securitypanelcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, hass, entity):
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.SecurityPanelController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "armState"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "armState":
            raise UnsupportedProperty(name)

        arm_state = self.entity.state
        if arm_state == STATE_ALARM_ARMED_HOME:
            return "ARMED_STAY"
        if arm_state == STATE_ALARM_ARMED_AWAY:
            return "ARMED_AWAY"
        if arm_state == STATE_ALARM_ARMED_NIGHT:
            return "ARMED_NIGHT"
        if arm_state == STATE_ALARM_ARMED_CUSTOM_BYPASS:
            return "ARMED_STAY"
        return "DISARMED"

    def configuration(self):
        """Return configuration object with supported authorization types."""
        code_format = self.entity.attributes.get(ATTR_CODE_FORMAT)
        supported = self.entity.attributes[ATTR_SUPPORTED_FEATURES]
        configuration = {}

        supported_arm_states = [{"value": "DISARMED"}]
        if supported & SUPPORT_ALARM_ARM_AWAY:
            supported_arm_states.append({"value": "ARMED_AWAY"})
        if supported & SUPPORT_ALARM_ARM_HOME:
            supported_arm_states.append({"value": "ARMED_STAY"})
        if supported & SUPPORT_ALARM_ARM_NIGHT:
            supported_arm_states.append({"value": "ARMED_NIGHT"})

        configuration["supportedArmStates"] = supported_arm_states

        if code_format == FORMAT_NUMBER:
            configuration["supportedAuthorizationTypes"] = [{"type": "FOUR_DIGIT_PIN"}]

        return configuration


class AlexaModeController(AlexaCapability):
    """Implements Alexa.ModeController.

    The instance property must be unique across ModeController, RangeController, ToggleController within the same device.
    The instance property should be a concatenated string of device domain period and single word.
    e.g. fan.speed & fan.direction.

    The instance property must not contain words from other instance property strings within the same device.
    e.g. Instance property cover.position & cover.tilt_position will cause the Alexa.Discovery directive to fail.

    An instance property string value may be reused for different devices.

    https://developer.amazon.com/docs/device-apis/alexa-modecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "fr-CA",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def __init__(self, entity, instance, non_controllable=False):
        """Initialize the entity."""
        super().__init__(entity, instance)
        self._resource = None
        self._semantics = None
        self.properties_non_controllable = lambda: non_controllable

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.ModeController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "mode"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "mode":
            raise UnsupportedProperty(name)

        # Fan Direction
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_DIRECTION}":
            mode = self.entity.attributes.get(fan.ATTR_DIRECTION, None)
            if mode in (fan.DIRECTION_FORWARD, fan.DIRECTION_REVERSE, STATE_UNKNOWN):
                return f"{fan.ATTR_DIRECTION}.{mode}"

        # Fan preset_mode
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_PRESET_MODE}":
            mode = self.entity.attributes.get(fan.ATTR_PRESET_MODE, None)
            if mode in self.entity.attributes.get(fan.ATTR_PRESET_MODES, None):
                return f"{fan.ATTR_PRESET_MODE}.{mode}"

        # Cover Position
        if self.instance == f"{cover.DOMAIN}.{cover.ATTR_POSITION}":
            # Return state instead of position when using ModeController.
            mode = self.entity.state
            if mode in (
                cover.STATE_OPEN,
                cover.STATE_OPENING,
                cover.STATE_CLOSED,
                cover.STATE_CLOSING,
                STATE_UNKNOWN,
            ):
                return f"{cover.ATTR_POSITION}.{mode}"

        return None

    def configuration(self):
        """Return configuration with modeResources."""
        if isinstance(self._resource, AlexaCapabilityResource):
            return self._resource.serialize_configuration()

        return None

    def capability_resources(self):
        """Return capabilityResources object."""

        # Fan Direction Resource
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_DIRECTION}":
            self._resource = AlexaModeResource(
                [AlexaGlobalCatalog.SETTING_DIRECTION], False
            )
            self._resource.add_mode(
                f"{fan.ATTR_DIRECTION}.{fan.DIRECTION_FORWARD}", [fan.DIRECTION_FORWARD]
            )
            self._resource.add_mode(
                f"{fan.ATTR_DIRECTION}.{fan.DIRECTION_REVERSE}", [fan.DIRECTION_REVERSE]
            )
            return self._resource.serialize_capability_resources()

        # Fan preset_mode
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_PRESET_MODE}":
            self._resource = AlexaModeResource(
                [AlexaGlobalCatalog.SETTING_PRESET], False
            )
            for preset_mode in self.entity.attributes.get(fan.ATTR_PRESET_MODES, []):
                self._resource.add_mode(
                    f"{fan.ATTR_PRESET_MODE}.{preset_mode}", [preset_mode]
                )
            return self._resource.serialize_capability_resources()

        # Cover Position Resources
        if self.instance == f"{cover.DOMAIN}.{cover.ATTR_POSITION}":
            self._resource = AlexaModeResource(
                ["Position", AlexaGlobalCatalog.SETTING_OPENING], False
            )
            self._resource.add_mode(
                f"{cover.ATTR_POSITION}.{cover.STATE_OPEN}",
                [AlexaGlobalCatalog.VALUE_OPEN],
            )
            self._resource.add_mode(
                f"{cover.ATTR_POSITION}.{cover.STATE_CLOSED}",
                [AlexaGlobalCatalog.VALUE_CLOSE],
            )
            self._resource.add_mode(
                f"{cover.ATTR_POSITION}.custom",
                ["Custom", AlexaGlobalCatalog.SETTING_PRESET],
            )
            return self._resource.serialize_capability_resources()

        return None

    def semantics(self):
        """Build and return semantics object."""
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        # Cover Position
        if self.instance == f"{cover.DOMAIN}.{cover.ATTR_POSITION}":
            lower_labels = [AlexaSemantics.ACTION_LOWER]
            raise_labels = [AlexaSemantics.ACTION_RAISE]
            self._semantics = AlexaSemantics()

            # Add open/close semantics if tilt is not supported.
            if not supported & cover.SUPPORT_SET_TILT_POSITION:
                lower_labels.append(AlexaSemantics.ACTION_CLOSE)
                raise_labels.append(AlexaSemantics.ACTION_OPEN)
                self._semantics.add_states_to_value(
                    [AlexaSemantics.STATES_CLOSED],
                    f"{cover.ATTR_POSITION}.{cover.STATE_CLOSED}",
                )
                self._semantics.add_states_to_value(
                    [AlexaSemantics.STATES_OPEN],
                    f"{cover.ATTR_POSITION}.{cover.STATE_OPEN}",
                )

            self._semantics.add_action_to_directive(
                lower_labels,
                "SetMode",
                {"mode": f"{cover.ATTR_POSITION}.{cover.STATE_CLOSED}"},
            )
            self._semantics.add_action_to_directive(
                raise_labels,
                "SetMode",
                {"mode": f"{cover.ATTR_POSITION}.{cover.STATE_OPEN}"},
            )

            return self._semantics.serialize_semantics()

        return None


class AlexaRangeController(AlexaCapability):
    """Implements Alexa.RangeController.

    The instance property must be unique across ModeController, RangeController, ToggleController within the same device.
    The instance property should be a concatenated string of device domain period and single word.
    e.g. fan.speed & fan.direction.

    The instance property must not contain words from other instance property strings within the same device.
    e.g. Instance property cover.position & cover.tilt_position will cause the Alexa.Discovery directive to fail.

    An instance property string value may be reused for different devices.

    https://developer.amazon.com/docs/device-apis/alexa-rangecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "fr-CA",
        "fr-FR",
        "it-IT",
        "ja-JP",
    }

    def __init__(self, entity, instance, non_controllable=False):
        """Initialize the entity."""
        super().__init__(entity, instance)
        self._resource = None
        self._semantics = None
        self.properties_non_controllable = lambda: non_controllable

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.RangeController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "rangeValue"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "rangeValue":
            raise UnsupportedProperty(name)

        # Return None for unavailable and unknown states.
        # Allows the Alexa.EndpointHealth Interface to handle the unavailable state in a stateReport.
        if self.entity.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None):
            return None

        # Fan Speed
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_SPEED}":
            speed_list = self.entity.attributes.get(fan.ATTR_SPEED_LIST)
            speed = self.entity.attributes.get(fan.ATTR_SPEED)
            if speed_list is not None and speed is not None:
                speed_index = next(
                    (i for i, v in enumerate(speed_list) if v == speed), None
                )
                return speed_index

        # Cover Position
        if self.instance == f"{cover.DOMAIN}.{cover.ATTR_POSITION}":
            return self.entity.attributes.get(cover.ATTR_CURRENT_POSITION)

        # Cover Tilt
        if self.instance == f"{cover.DOMAIN}.tilt":
            return self.entity.attributes.get(cover.ATTR_CURRENT_TILT_POSITION)

        # Input Number Value
        if self.instance == f"{input_number.DOMAIN}.{input_number.ATTR_VALUE}":
            return float(self.entity.state)

        # Vacuum Fan Speed
        if self.instance == f"{vacuum.DOMAIN}.{vacuum.ATTR_FAN_SPEED}":
            speed_list = self.entity.attributes.get(vacuum.ATTR_FAN_SPEED_LIST)
            speed = self.entity.attributes.get(vacuum.ATTR_FAN_SPEED)
            if speed_list is not None and speed is not None:
                speed_index = next(
                    (i for i, v in enumerate(speed_list) if v == speed), None
                )
                return speed_index

        return None

    def configuration(self):
        """Return configuration with presetResources."""
        if isinstance(self._resource, AlexaCapabilityResource):
            return self._resource.serialize_configuration()

        return None

    def capability_resources(self):
        """Return capabilityResources object."""

        # Fan Speed Resources
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_SPEED}":
            speed_list = self.entity.attributes[fan.ATTR_SPEED_LIST]
            max_value = len(speed_list) - 1
            self._resource = AlexaPresetResource(
                labels=[AlexaGlobalCatalog.SETTING_FAN_SPEED],
                min_value=0,
                max_value=max_value,
                precision=1,
            )
            for index, speed in enumerate(speed_list):
                labels = []
                if isinstance(speed, str):
                    labels.append(speed.replace("_", " "))
                if index == 1:
                    labels.append(AlexaGlobalCatalog.VALUE_MINIMUM)
                if index == max_value:
                    labels.append(AlexaGlobalCatalog.VALUE_MAXIMUM)

                if len(labels) > 0:
                    self._resource.add_preset(value=index, labels=labels)

            return self._resource.serialize_capability_resources()

        # Cover Position Resources
        if self.instance == f"{cover.DOMAIN}.{cover.ATTR_POSITION}":
            self._resource = AlexaPresetResource(
                ["Position", AlexaGlobalCatalog.SETTING_OPENING],
                min_value=0,
                max_value=100,
                precision=1,
                unit=AlexaGlobalCatalog.UNIT_PERCENT,
            )
            return self._resource.serialize_capability_resources()

        # Cover Tilt Resources
        if self.instance == f"{cover.DOMAIN}.tilt":
            self._resource = AlexaPresetResource(
                ["Tilt", "Angle", AlexaGlobalCatalog.SETTING_DIRECTION],
                min_value=0,
                max_value=100,
                precision=1,
                unit=AlexaGlobalCatalog.UNIT_PERCENT,
            )
            return self._resource.serialize_capability_resources()

        # Input Number Value
        if self.instance == f"{input_number.DOMAIN}.{input_number.ATTR_VALUE}":
            min_value = float(self.entity.attributes[input_number.ATTR_MIN])
            max_value = float(self.entity.attributes[input_number.ATTR_MAX])
            precision = float(self.entity.attributes.get(input_number.ATTR_STEP, 1))
            unit = self.entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

            self._resource = AlexaPresetResource(
                ["Value", AlexaGlobalCatalog.SETTING_PRESET],
                min_value=min_value,
                max_value=max_value,
                precision=precision,
                unit=unit,
            )
            self._resource.add_preset(
                value=min_value, labels=[AlexaGlobalCatalog.VALUE_MINIMUM]
            )
            self._resource.add_preset(
                value=max_value, labels=[AlexaGlobalCatalog.VALUE_MAXIMUM]
            )
            return self._resource.serialize_capability_resources()

        # Vacuum Fan Speed Resources
        if self.instance == f"{vacuum.DOMAIN}.{vacuum.ATTR_FAN_SPEED}":
            speed_list = self.entity.attributes[vacuum.ATTR_FAN_SPEED_LIST]
            max_value = len(speed_list) - 1
            self._resource = AlexaPresetResource(
                labels=[AlexaGlobalCatalog.SETTING_FAN_SPEED],
                min_value=0,
                max_value=max_value,
                precision=1,
            )
            for index, speed in enumerate(speed_list):
                labels = [speed.replace("_", " ")]
                if index == 1:
                    labels.append(AlexaGlobalCatalog.VALUE_MINIMUM)
                if index == max_value:
                    labels.append(AlexaGlobalCatalog.VALUE_MAXIMUM)
                self._resource.add_preset(value=index, labels=labels)

            return self._resource.serialize_capability_resources()

        return None

    def semantics(self):
        """Build and return semantics object."""
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        # Cover Position
        if self.instance == f"{cover.DOMAIN}.{cover.ATTR_POSITION}":
            lower_labels = [AlexaSemantics.ACTION_LOWER]
            raise_labels = [AlexaSemantics.ACTION_RAISE]
            self._semantics = AlexaSemantics()

            # Add open/close semantics if tilt is not supported.
            if not supported & cover.SUPPORT_SET_TILT_POSITION:
                lower_labels.append(AlexaSemantics.ACTION_CLOSE)
                raise_labels.append(AlexaSemantics.ACTION_OPEN)
                self._semantics.add_states_to_value(
                    [AlexaSemantics.STATES_CLOSED], value=0
                )
                self._semantics.add_states_to_range(
                    [AlexaSemantics.STATES_OPEN], min_value=1, max_value=100
                )

            self._semantics.add_action_to_directive(
                lower_labels, "SetRangeValue", {"rangeValue": 0}
            )
            self._semantics.add_action_to_directive(
                raise_labels, "SetRangeValue", {"rangeValue": 100}
            )
            return self._semantics.serialize_semantics()

        # Cover Tilt
        if self.instance == f"{cover.DOMAIN}.tilt":
            self._semantics = AlexaSemantics()
            self._semantics.add_action_to_directive(
                [AlexaSemantics.ACTION_CLOSE], "SetRangeValue", {"rangeValue": 0}
            )
            self._semantics.add_action_to_directive(
                [AlexaSemantics.ACTION_OPEN], "SetRangeValue", {"rangeValue": 100}
            )
            self._semantics.add_states_to_value([AlexaSemantics.STATES_CLOSED], value=0)
            self._semantics.add_states_to_range(
                [AlexaSemantics.STATES_OPEN], min_value=1, max_value=100
            )
            return self._semantics.serialize_semantics()

        return None


class AlexaToggleController(AlexaCapability):
    """Implements Alexa.ToggleController.

    The instance property must be unique across ModeController, RangeController, ToggleController within the same device.
    The instance property should be a concatenated string of device domain period and single word.
    e.g. fan.speed & fan.direction.

    The instance property must not contain words from other instance property strings within the same device.
    e.g. Instance property cover.position & cover.tilt_position will cause the Alexa.Discovery directive to fail.

    An instance property string value may be reused for different devices.

    https://developer.amazon.com/docs/device-apis/alexa-togglecontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "fr-CA",
        "fr-FR",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def __init__(self, entity, instance, non_controllable=False):
        """Initialize the entity."""
        super().__init__(entity, instance)
        self._resource = None
        self._semantics = None
        self.properties_non_controllable = lambda: non_controllable

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.ToggleController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "toggleState"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "toggleState":
            raise UnsupportedProperty(name)

        # Fan Oscillating
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_OSCILLATING}":
            is_on = bool(self.entity.attributes.get(fan.ATTR_OSCILLATING))
            return "ON" if is_on else "OFF"

        return None

    def capability_resources(self):
        """Return capabilityResources object."""

        # Fan Oscillating Resource
        if self.instance == f"{fan.DOMAIN}.{fan.ATTR_OSCILLATING}":
            self._resource = AlexaCapabilityResource(
                [AlexaGlobalCatalog.SETTING_OSCILLATE, "Rotate", "Rotation"]
            )
            return self._resource.serialize_capability_resources()

        return None


class AlexaChannelController(AlexaCapability):
    """Implements Alexa.ChannelController.

    https://developer.amazon.com/docs/device-apis/alexa-channelcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.ChannelController"


class AlexaDoorbellEventSource(AlexaCapability):
    """Implements Alexa.DoorbellEventSource.

    https://developer.amazon.com/docs/device-apis/alexa-doorbelleventsource.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "es-MX",
        "es-US",
        "fr-CA",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.DoorbellEventSource"

    def capability_proactively_reported(self):
        """Return True for proactively reported capability."""
        return True


class AlexaPlaybackStateReporter(AlexaCapability):
    """Implements Alexa.PlaybackStateReporter.

    https://developer.amazon.com/docs/device-apis/alexa-playbackstatereporter.html
    """

    supported_locales = {"de-DE", "en-GB", "en-US", "es-MX", "fr-FR"}

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.PlaybackStateReporter"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "playbackState"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "playbackState":
            raise UnsupportedProperty(name)

        playback_state = self.entity.state
        if playback_state == STATE_PLAYING:
            return {"state": "PLAYING"}
        if playback_state == STATE_PAUSED:
            return {"state": "PAUSED"}

        return {"state": "STOPPED"}


class AlexaSeekController(AlexaCapability):
    """Implements Alexa.SeekController.

    https://developer.amazon.com/docs/device-apis/alexa-seekcontroller.html
    """

    supported_locales = {"de-DE", "en-GB", "en-US", "es-MX"}

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.SeekController"


class AlexaEventDetectionSensor(AlexaCapability):
    """Implements Alexa.EventDetectionSensor.

    https://developer.amazon.com/docs/device-apis/alexa-eventdetectionsensor.html
    """

    supported_locales = {"en-US"}

    def __init__(self, hass, entity):
        """Initialize the entity."""
        super().__init__(entity)
        self.hass = hass

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.EventDetectionSensor"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "humanPresenceDetectionState"}]

    def properties_proactively_reported(self):
        """Return True if properties asynchronously reported."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "humanPresenceDetectionState":
            raise UnsupportedProperty(name)

        human_presence = "NOT_DETECTED"
        state = self.entity.state

        # Return None for unavailable and unknown states.
        # Allows the Alexa.EndpointHealth Interface to handle the unavailable state in a stateReport.
        if state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None):
            return None

        if self.entity.domain == image_processing.DOMAIN:
            if int(state):
                human_presence = "DETECTED"
        elif state == STATE_ON:
            human_presence = "DETECTED"

        return {"value": human_presence}

    def configuration(self):
        """Return supported detection types."""
        return {
            "detectionMethods": ["AUDIO", "VIDEO"],
            "detectionModes": {
                "humanPresence": {
                    "featureAvailability": "ENABLED",
                    "supportsNotDetected": True,
                }
            },
        }


class AlexaEqualizerController(AlexaCapability):
    """Implements Alexa.EqualizerController.

    https://developer.amazon.com/en-US/docs/alexa/device-apis/alexa-equalizercontroller.html
    """

    supported_locales = {"de-DE", "en-IN", "en-US", "es-ES", "it-IT", "ja-JP", "pt-BR"}
    VALID_SOUND_MODES = {
        "MOVIE",
        "MUSIC",
        "NIGHT",
        "SPORT",
        "TV",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.EqualizerController"

    def properties_supported(self):
        """Return what properties this entity supports.

        Either bands, mode or both can be specified. Only mode is supported at this time.
        """
        return [{"name": "mode"}]

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "mode":
            raise UnsupportedProperty(name)

        sound_mode = self.entity.attributes.get(media_player.ATTR_SOUND_MODE)
        if sound_mode and sound_mode.upper() in self.VALID_SOUND_MODES:
            return sound_mode.upper()

        return None

    def configurations(self):
        """Return the sound modes supported in the configurations object."""
        configurations = None
        supported_sound_modes = self.get_valid_inputs(
            self.entity.attributes.get(media_player.ATTR_SOUND_MODE_LIST, [])
        )
        if supported_sound_modes:
            configurations = {"modes": {"supported": supported_sound_modes}}

        return configurations

    @classmethod
    def get_valid_inputs(cls, sound_mode_list):
        """Return list of supported inputs."""
        input_list = []
        for sound_mode in sound_mode_list:
            sound_mode = sound_mode.upper()

            if sound_mode in cls.VALID_SOUND_MODES:
                input_list.append({"name": sound_mode})

        return input_list


class AlexaTimeHoldController(AlexaCapability):
    """Implements Alexa.TimeHoldController.

    https://developer.amazon.com/docs/device-apis/alexa-timeholdcontroller.html
    """

    supported_locales = {"en-US"}

    def __init__(self, entity, allow_remote_resume=False):
        """Initialize the entity."""
        super().__init__(entity)
        self._allow_remote_resume = allow_remote_resume

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.TimeHoldController"

    def configuration(self):
        """Return configuration object.

        Set allowRemoteResume to True if Alexa can restart the operation on the device.
        When false, Alexa does not send the Resume directive.
        """
        return {"allowRemoteResume": self._allow_remote_resume}


class AlexaCameraStreamController(AlexaCapability):
    """Implements Alexa.CameraStreamController.

    https://developer.amazon.com/docs/device-apis/alexa-camerastreamcontroller.html
    """

    supported_locales = {
        "de-DE",
        "en-AU",
        "en-CA",
        "en-GB",
        "en-IN",
        "en-US",
        "es-ES",
        "fr-FR",
        "hi-IN",
        "it-IT",
        "ja-JP",
        "pt-BR",
    }

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.CameraStreamController"

    def camera_stream_configurations(self):
        """Return cameraStreamConfigurations object."""
        return [
            {
                "protocols": ["HLS"],
                "resolutions": [{"width": 1280, "height": 720}],
                "authorizationTypes": ["NONE"],
                "videoCodecs": ["H264"],
                "audioCodecs": ["AAC"],
            }
        ]
