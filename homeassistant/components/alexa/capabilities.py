"""Alexa capabilities."""
from datetime import datetime
import logging

from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_LOCKED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNLOCKED,
)
import homeassistant.components.climate.const as climate
from homeassistant.components import light, fan, cover
import homeassistant.util.color as color_util

from .const import (
    API_TEMP_UNITS,
    API_THERMOSTAT_MODES,
    API_THERMOSTAT_PRESETS,
    DATE_FORMAT,
    PERCENTAGE_FAN_MAP,
)
from .errors import UnsupportedProperty


_LOGGER = logging.getLogger(__name__)


class AlexaCapibility:
    """Base class for Alexa capability interfaces.

    The Smart Home Skills API defines a number of "capability interfaces",
    roughly analogous to domains in Home Assistant. The supported interfaces
    describe what actions can be performed on a particular device.

    https://developer.amazon.com/docs/device-apis/message-guide.html
    """

    def __init__(self, entity):
        """Initialize an Alexa capibility."""
        self.entity = entity

    def name(self):
        """Return the Alexa API name of this interface."""
        raise NotImplementedError

    @staticmethod
    def properties_supported():
        """Return what properties this entity supports."""
        return []

    @staticmethod
    def properties_proactively_reported():
        """Return True if properties asynchronously reported."""
        return False

    @staticmethod
    def properties_retrievable():
        """Return True if properties can be retrieved."""
        return False

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

    def serialize_discovery(self):
        """Serialize according to the Discovery API."""
        result = {
            "type": "AlexaInterface",
            "interface": self.name(),
            "version": "3",
            "properties": {
                "supported": self.properties_supported(),
                "proactivelyReported": self.properties_proactively_reported(),
                "retrievable": self.properties_retrievable(),
            },
        }

        # pylint: disable=assignment-from-none
        supports_deactivation = self.supports_deactivation()
        if supports_deactivation is not None:
            result["supportsDeactivation"] = supports_deactivation
        return result

    def serialize_properties(self):
        """Return properties serialized for an API response."""
        for prop in self.properties_supported():
            prop_name = prop["name"]
            # pylint: disable=assignment-from-no-return
            prop_value = self.get_property(prop_name)
            if prop_value is not None:
                yield {
                    "name": prop_name,
                    "namespace": self.name(),
                    "value": prop_value,
                    "timeOfSample": datetime.now().strftime(DATE_FORMAT),
                    "uncertaintyInMilliseconds": 0,
                }


class AlexaEndpointHealth(AlexaCapibility):
    """Implements Alexa.EndpointHealth.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#report-state-when-alexa-requests-it
    """

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
        return False

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


class AlexaPowerController(AlexaCapibility):
    """Implements Alexa.PowerController.

    https://developer.amazon.com/docs/device-apis/alexa-powercontroller.html
    """

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

        else:
            is_on = self.entity.state != STATE_OFF

        return "ON" if is_on else "OFF"


class AlexaLockController(AlexaCapibility):
    """Implements Alexa.LockController.

    https://developer.amazon.com/docs/device-apis/alexa-lockcontroller.html
    """

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


class AlexaSceneController(AlexaCapibility):
    """Implements Alexa.SceneController.

    https://developer.amazon.com/docs/device-apis/alexa-scenecontroller.html
    """

    def __init__(self, entity, supports_deactivation):
        """Initialize the entity."""
        super().__init__(entity)
        self.supports_deactivation = lambda: supports_deactivation

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.SceneController"


class AlexaBrightnessController(AlexaCapibility):
    """Implements Alexa.BrightnessController.

    https://developer.amazon.com/docs/device-apis/alexa-brightnesscontroller.html
    """

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


class AlexaColorController(AlexaCapibility):
    """Implements Alexa.ColorController.

    https://developer.amazon.com/docs/device-apis/alexa-colorcontroller.html
    """

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.ColorController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "color"}]

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


class AlexaColorTemperatureController(AlexaCapibility):
    """Implements Alexa.ColorTemperatureController.

    https://developer.amazon.com/docs/device-apis/alexa-colortemperaturecontroller.html
    """

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.ColorTemperatureController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "colorTemperatureInKelvin"}]

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
        return 0


class AlexaPercentageController(AlexaCapibility):
    """Implements Alexa.PercentageController.

    https://developer.amazon.com/docs/device-apis/alexa-percentagecontroller.html
    """

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.PercentageController"

    def properties_supported(self):
        """Return what properties this entity supports."""
        return [{"name": "percentage"}]

    def properties_retrievable(self):
        """Return True if properties can be retrieved."""
        return True

    def get_property(self, name):
        """Read and return a property."""
        if name != "percentage":
            raise UnsupportedProperty(name)

        if self.entity.domain == fan.DOMAIN:
            speed = self.entity.attributes.get(fan.ATTR_SPEED)

            return PERCENTAGE_FAN_MAP.get(speed, 0)

        if self.entity.domain == cover.DOMAIN:
            return self.entity.attributes.get(cover.ATTR_CURRENT_POSITION, 0)

        return 0


class AlexaSpeaker(AlexaCapibility):
    """Implements Alexa.Speaker.

    https://developer.amazon.com/docs/device-apis/alexa-speaker.html
    """

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.Speaker"


class AlexaStepSpeaker(AlexaCapibility):
    """Implements Alexa.StepSpeaker.

    https://developer.amazon.com/docs/device-apis/alexa-stepspeaker.html
    """

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.StepSpeaker"


class AlexaPlaybackController(AlexaCapibility):
    """Implements Alexa.PlaybackController.

    https://developer.amazon.com/docs/device-apis/alexa-playbackcontroller.html
    """

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.PlaybackController"


class AlexaInputController(AlexaCapibility):
    """Implements Alexa.InputController.

    https://developer.amazon.com/docs/device-apis/alexa-inputcontroller.html
    """

    def name(self):
        """Return the Alexa API name of this interface."""
        return "Alexa.InputController"


class AlexaTemperatureSensor(AlexaCapibility):
    """Implements Alexa.TemperatureSensor.

    https://developer.amazon.com/docs/device-apis/alexa-temperaturesensor.html
    """

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
        return {"value": float(temp), "scale": API_TEMP_UNITS[unit]}


class AlexaContactSensor(AlexaCapibility):
    """Implements Alexa.ContactSensor.

    The Alexa.ContactSensor interface describes the properties and events used
    to report the state of an endpoint that detects contact between two
    surfaces. For example, a contact sensor can report whether a door or window
    is open.

    https://developer.amazon.com/docs/device-apis/alexa-contactsensor.html
    """

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


class AlexaMotionSensor(AlexaCapibility):
    """Implements Alexa.MotionSensor.

    https://developer.amazon.com/docs/device-apis/alexa-motionsensor.html
    """

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


class AlexaThermostatController(AlexaCapibility):
    """Implements Alexa.ThermostatController.

    https://developer.amazon.com/docs/device-apis/alexa-thermostatcontroller.html
    """

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

        return {"value": float(temp), "scale": API_TEMP_UNITS[unit]}
