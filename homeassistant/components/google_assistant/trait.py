"""Implement the Google Smart Home traits."""
import logging
from typing import List, Optional

from homeassistant.components import (
    alarm_control_panel,
    binary_sensor,
    camera,
    cover,
    fan,
    group,
    input_boolean,
    input_select,
    light,
    lock,
    media_player,
    scene,
    script,
    sensor,
    switch,
    vacuum,
)
from homeassistant.components.climate import const as climate
from homeassistant.components.humidifier import const as humidifier
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_CODE,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    STATE_IDLE,
    STATE_LOCKED,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import DOMAIN as HA_DOMAIN
from homeassistant.helpers.network import get_url
from homeassistant.util import color as color_util, dt, temperature as temp_util

from .const import (
    CHALLENGE_ACK_NEEDED,
    CHALLENGE_FAILED_PIN_NEEDED,
    CHALLENGE_PIN_NEEDED,
    ERR_ALREADY_ARMED,
    ERR_ALREADY_DISARMED,
    ERR_CHALLENGE_NOT_SETUP,
    ERR_FUNCTION_NOT_SUPPORTED,
    ERR_NOT_SUPPORTED,
    ERR_UNSUPPORTED_INPUT,
    ERR_VALUE_OUT_OF_RANGE,
)
from .error import ChallengeNeeded, SmartHomeError

_LOGGER = logging.getLogger(__name__)

PREFIX_TRAITS = "action.devices.traits."
TRAIT_CAMERA_STREAM = f"{PREFIX_TRAITS}CameraStream"
TRAIT_ONOFF = f"{PREFIX_TRAITS}OnOff"
TRAIT_DOCK = f"{PREFIX_TRAITS}Dock"
TRAIT_STARTSTOP = f"{PREFIX_TRAITS}StartStop"
TRAIT_BRIGHTNESS = f"{PREFIX_TRAITS}Brightness"
TRAIT_COLOR_SETTING = f"{PREFIX_TRAITS}ColorSetting"
TRAIT_SCENE = f"{PREFIX_TRAITS}Scene"
TRAIT_TEMPERATURE_SETTING = f"{PREFIX_TRAITS}TemperatureSetting"
TRAIT_LOCKUNLOCK = f"{PREFIX_TRAITS}LockUnlock"
TRAIT_FANSPEED = f"{PREFIX_TRAITS}FanSpeed"
TRAIT_MODES = f"{PREFIX_TRAITS}Modes"
TRAIT_INPUTSELECTOR = f"{PREFIX_TRAITS}InputSelector"
TRAIT_OPENCLOSE = f"{PREFIX_TRAITS}OpenClose"
TRAIT_VOLUME = f"{PREFIX_TRAITS}Volume"
TRAIT_ARMDISARM = f"{PREFIX_TRAITS}ArmDisarm"
TRAIT_HUMIDITY_SETTING = f"{PREFIX_TRAITS}HumiditySetting"
TRAIT_TRANSPORT_CONTROL = f"{PREFIX_TRAITS}TransportControl"
TRAIT_MEDIA_STATE = f"{PREFIX_TRAITS}MediaState"

PREFIX_COMMANDS = "action.devices.commands."
COMMAND_ONOFF = f"{PREFIX_COMMANDS}OnOff"
COMMAND_GET_CAMERA_STREAM = f"{PREFIX_COMMANDS}GetCameraStream"
COMMAND_DOCK = f"{PREFIX_COMMANDS}Dock"
COMMAND_STARTSTOP = f"{PREFIX_COMMANDS}StartStop"
COMMAND_PAUSEUNPAUSE = f"{PREFIX_COMMANDS}PauseUnpause"
COMMAND_BRIGHTNESS_ABSOLUTE = f"{PREFIX_COMMANDS}BrightnessAbsolute"
COMMAND_COLOR_ABSOLUTE = f"{PREFIX_COMMANDS}ColorAbsolute"
COMMAND_ACTIVATE_SCENE = f"{PREFIX_COMMANDS}ActivateScene"
COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT = (
    f"{PREFIX_COMMANDS}ThermostatTemperatureSetpoint"
)
COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE = (
    f"{PREFIX_COMMANDS}ThermostatTemperatureSetRange"
)
COMMAND_THERMOSTAT_SET_MODE = f"{PREFIX_COMMANDS}ThermostatSetMode"
COMMAND_LOCKUNLOCK = f"{PREFIX_COMMANDS}LockUnlock"
COMMAND_FANSPEED = f"{PREFIX_COMMANDS}SetFanSpeed"
COMMAND_MODES = f"{PREFIX_COMMANDS}SetModes"
COMMAND_INPUT = f"{PREFIX_COMMANDS}SetInput"
COMMAND_NEXT_INPUT = f"{PREFIX_COMMANDS}NextInput"
COMMAND_PREVIOUS_INPUT = f"{PREFIX_COMMANDS}PreviousInput"
COMMAND_OPENCLOSE = f"{PREFIX_COMMANDS}OpenClose"
COMMAND_SET_VOLUME = f"{PREFIX_COMMANDS}setVolume"
COMMAND_VOLUME_RELATIVE = f"{PREFIX_COMMANDS}volumeRelative"
COMMAND_ARMDISARM = f"{PREFIX_COMMANDS}ArmDisarm"
COMMAND_MEDIA_NEXT = f"{PREFIX_COMMANDS}mediaNext"
COMMAND_MEDIA_PAUSE = f"{PREFIX_COMMANDS}mediaPause"
COMMAND_MEDIA_PREVIOUS = f"{PREFIX_COMMANDS}mediaPrevious"
COMMAND_MEDIA_RESUME = f"{PREFIX_COMMANDS}mediaResume"
COMMAND_MEDIA_SEEK_RELATIVE = f"{PREFIX_COMMANDS}mediaSeekRelative"
COMMAND_MEDIA_SEEK_TO_POSITION = f"{PREFIX_COMMANDS}mediaSeekToPosition"
COMMAND_MEDIA_SHUFFLE = f"{PREFIX_COMMANDS}mediaShuffle"
COMMAND_MEDIA_STOP = f"{PREFIX_COMMANDS}mediaStop"
COMMAND_SET_HUMIDITY = f"{PREFIX_COMMANDS}SetHumidity"


TRAITS = []


def register_trait(trait):
    """Decorate a function to register a trait."""
    TRAITS.append(trait)
    return trait


def _google_temp_unit(units):
    """Return Google temperature unit."""
    if units == TEMP_FAHRENHEIT:
        return "F"
    return "C"


def _next_selected(items: List[str], selected: Optional[str]) -> Optional[str]:
    """Return the next item in a item list starting at given value.

    If selected is missing in items, None is returned
    """
    try:
        index = items.index(selected)
    except ValueError:
        return None

    next_item = 0 if index == len(items) - 1 else index + 1
    return items[next_item]


class _Trait:
    """Represents a Trait inside Google Assistant skill."""

    commands = []

    @staticmethod
    def might_2fa(domain, features, device_class):
        """Return if the trait might ask for 2FA."""
        return False

    def __init__(self, hass, state, config):
        """Initialize a trait for a state."""
        self.hass = hass
        self.state = state
        self.config = config

    def sync_attributes(self):
        """Return attributes for a sync request."""
        raise NotImplementedError

    def query_attributes(self):
        """Return the attributes of this trait for this entity."""
        raise NotImplementedError

    def can_execute(self, command, params):
        """Test if command can be executed."""
        return command in self.commands

    async def execute(self, command, data, params, challenge):
        """Execute a trait command."""
        raise NotImplementedError


@register_trait
class BrightnessTrait(_Trait):
    """Trait to control brightness of a device.

    https://developers.google.com/actions/smarthome/traits/brightness
    """

    name = TRAIT_BRIGHTNESS
    commands = [COMMAND_BRIGHTNESS_ABSOLUTE]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == light.DOMAIN:
            return features & light.SUPPORT_BRIGHTNESS

        return False

    def sync_attributes(self):
        """Return brightness attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return brightness query attributes."""
        domain = self.state.domain
        response = {}

        if domain == light.DOMAIN:
            brightness = self.state.attributes.get(light.ATTR_BRIGHTNESS)
            if brightness is not None:
                response["brightness"] = int(100 * (brightness / 255))
            else:
                response["brightness"] = 0

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a brightness command."""
        domain = self.state.domain

        if domain == light.DOMAIN:
            await self.hass.services.async_call(
                light.DOMAIN,
                light.SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    light.ATTR_BRIGHTNESS_PCT: params["brightness"],
                },
                blocking=True,
                context=data.context,
            )


@register_trait
class CameraStreamTrait(_Trait):
    """Trait to stream from cameras.

    https://developers.google.com/actions/smarthome/traits/camerastream
    """

    name = TRAIT_CAMERA_STREAM
    commands = [COMMAND_GET_CAMERA_STREAM]

    stream_info = None

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == camera.DOMAIN:
            return features & camera.SUPPORT_STREAM

        return False

    def sync_attributes(self):
        """Return stream attributes for a sync request."""
        return {
            "cameraStreamSupportedProtocols": ["hls"],
            "cameraStreamNeedAuthToken": False,
            "cameraStreamNeedDrmEncryption": False,
        }

    def query_attributes(self):
        """Return camera stream attributes."""
        return self.stream_info or {}

    async def execute(self, command, data, params, challenge):
        """Execute a get camera stream command."""
        url = await self.hass.components.camera.async_request_stream(
            self.state.entity_id, "hls"
        )
        self.stream_info = {"cameraStreamAccessUrl": f"{get_url(self.hass)}{url}"}


@register_trait
class OnOffTrait(_Trait):
    """Trait to offer basic on and off functionality.

    https://developers.google.com/actions/smarthome/traits/onoff
    """

    name = TRAIT_ONOFF
    commands = [COMMAND_ONOFF]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        return domain in (
            group.DOMAIN,
            input_boolean.DOMAIN,
            switch.DOMAIN,
            fan.DOMAIN,
            light.DOMAIN,
            media_player.DOMAIN,
            humidifier.DOMAIN,
        )

    def sync_attributes(self):
        """Return OnOff attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return OnOff query attributes."""
        return {"on": self.state.state not in (STATE_OFF, STATE_UNKNOWN)}

    async def execute(self, command, data, params, challenge):
        """Execute an OnOff command."""
        domain = self.state.domain

        if domain == group.DOMAIN:
            service_domain = HA_DOMAIN
            service = SERVICE_TURN_ON if params["on"] else SERVICE_TURN_OFF

        else:
            service_domain = domain
            service = SERVICE_TURN_ON if params["on"] else SERVICE_TURN_OFF

        await self.hass.services.async_call(
            service_domain,
            service,
            {ATTR_ENTITY_ID: self.state.entity_id},
            blocking=True,
            context=data.context,
        )


@register_trait
class ColorSettingTrait(_Trait):
    """Trait to offer color temperature functionality.

    https://developers.google.com/actions/smarthome/traits/colortemperature
    """

    name = TRAIT_COLOR_SETTING
    commands = [COMMAND_COLOR_ABSOLUTE]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain != light.DOMAIN:
            return False

        return features & light.SUPPORT_COLOR_TEMP or features & light.SUPPORT_COLOR

    def sync_attributes(self):
        """Return color temperature attributes for a sync request."""
        attrs = self.state.attributes
        features = attrs.get(ATTR_SUPPORTED_FEATURES, 0)
        response = {}

        if features & light.SUPPORT_COLOR:
            response["colorModel"] = "hsv"

        if features & light.SUPPORT_COLOR_TEMP:
            # Max Kelvin is Min Mireds K = 1000000 / mireds
            # Min Kelvin is Max Mireds K = 1000000 / mireds
            response["colorTemperatureRange"] = {
                "temperatureMaxK": color_util.color_temperature_mired_to_kelvin(
                    attrs.get(light.ATTR_MIN_MIREDS)
                ),
                "temperatureMinK": color_util.color_temperature_mired_to_kelvin(
                    attrs.get(light.ATTR_MAX_MIREDS)
                ),
            }

        return response

    def query_attributes(self):
        """Return color temperature query attributes."""
        features = self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        color = {}

        if features & light.SUPPORT_COLOR:
            color_hs = self.state.attributes.get(light.ATTR_HS_COLOR)
            brightness = self.state.attributes.get(light.ATTR_BRIGHTNESS, 1)
            if color_hs is not None:
                color["spectrumHsv"] = {
                    "hue": color_hs[0],
                    "saturation": color_hs[1] / 100,
                    "value": brightness / 255,
                }

        if features & light.SUPPORT_COLOR_TEMP:
            temp = self.state.attributes.get(light.ATTR_COLOR_TEMP)
            # Some faulty integrations might put 0 in here, raising exception.
            if temp == 0:
                _LOGGER.warning(
                    "Entity %s has incorrect color temperature %s",
                    self.state.entity_id,
                    temp,
                )
            elif temp is not None:
                color["temperatureK"] = color_util.color_temperature_mired_to_kelvin(
                    temp
                )

        response = {}

        if color:
            response["color"] = color

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a color temperature command."""
        if "temperature" in params["color"]:
            temp = color_util.color_temperature_kelvin_to_mired(
                params["color"]["temperature"]
            )
            min_temp = self.state.attributes[light.ATTR_MIN_MIREDS]
            max_temp = self.state.attributes[light.ATTR_MAX_MIREDS]

            if temp < min_temp or temp > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    f"Temperature should be between {min_temp} and {max_temp}",
                )

            await self.hass.services.async_call(
                light.DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: self.state.entity_id, light.ATTR_COLOR_TEMP: temp},
                blocking=True,
                context=data.context,
            )

        elif "spectrumRGB" in params["color"]:
            # Convert integer to hex format and left pad with 0's till length 6
            hex_value = f"{params['color']['spectrumRGB']:06x}"
            color = color_util.color_RGB_to_hs(
                *color_util.rgb_hex_to_rgb_list(hex_value)
            )

            await self.hass.services.async_call(
                light.DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: self.state.entity_id, light.ATTR_HS_COLOR: color},
                blocking=True,
                context=data.context,
            )

        elif "spectrumHSV" in params["color"]:
            color = params["color"]["spectrumHSV"]
            saturation = color["saturation"] * 100
            brightness = color["value"] * 255

            await self.hass.services.async_call(
                light.DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    light.ATTR_HS_COLOR: [color["hue"], saturation],
                    light.ATTR_BRIGHTNESS: brightness,
                },
                blocking=True,
                context=data.context,
            )


@register_trait
class SceneTrait(_Trait):
    """Trait to offer scene functionality.

    https://developers.google.com/actions/smarthome/traits/scene
    """

    name = TRAIT_SCENE
    commands = [COMMAND_ACTIVATE_SCENE]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        return domain in (scene.DOMAIN, script.DOMAIN)

    def sync_attributes(self):
        """Return scene attributes for a sync request."""
        # Neither supported domain can support sceneReversible
        return {}

    def query_attributes(self):
        """Return scene query attributes."""
        return {}

    async def execute(self, command, data, params, challenge):
        """Execute a scene command."""
        # Don't block for scripts as they can be slow.
        await self.hass.services.async_call(
            self.state.domain,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self.state.entity_id},
            blocking=self.state.domain != script.DOMAIN,
            context=data.context,
        )


@register_trait
class DockTrait(_Trait):
    """Trait to offer dock functionality.

    https://developers.google.com/actions/smarthome/traits/dock
    """

    name = TRAIT_DOCK
    commands = [COMMAND_DOCK]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        return domain == vacuum.DOMAIN

    def sync_attributes(self):
        """Return dock attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return dock query attributes."""
        return {"isDocked": self.state.state == vacuum.STATE_DOCKED}

    async def execute(self, command, data, params, challenge):
        """Execute a dock command."""
        await self.hass.services.async_call(
            self.state.domain,
            vacuum.SERVICE_RETURN_TO_BASE,
            {ATTR_ENTITY_ID: self.state.entity_id},
            blocking=True,
            context=data.context,
        )


@register_trait
class StartStopTrait(_Trait):
    """Trait to offer StartStop functionality.

    https://developers.google.com/actions/smarthome/traits/startstop
    """

    name = TRAIT_STARTSTOP
    commands = [COMMAND_STARTSTOP, COMMAND_PAUSEUNPAUSE]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        return domain == vacuum.DOMAIN

    def sync_attributes(self):
        """Return StartStop attributes for a sync request."""
        return {
            "pausable": self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            & vacuum.SUPPORT_PAUSE
            != 0
        }

    def query_attributes(self):
        """Return StartStop query attributes."""
        return {
            "isRunning": self.state.state == vacuum.STATE_CLEANING,
            "isPaused": self.state.state == vacuum.STATE_PAUSED,
        }

    async def execute(self, command, data, params, challenge):
        """Execute a StartStop command."""
        if command == COMMAND_STARTSTOP:
            if params["start"]:
                await self.hass.services.async_call(
                    self.state.domain,
                    vacuum.SERVICE_START,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=True,
                    context=data.context,
                )
            else:
                await self.hass.services.async_call(
                    self.state.domain,
                    vacuum.SERVICE_STOP,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=True,
                    context=data.context,
                )
        elif command == COMMAND_PAUSEUNPAUSE:
            if params["pause"]:
                await self.hass.services.async_call(
                    self.state.domain,
                    vacuum.SERVICE_PAUSE,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=True,
                    context=data.context,
                )
            else:
                await self.hass.services.async_call(
                    self.state.domain,
                    vacuum.SERVICE_START,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=True,
                    context=data.context,
                )


@register_trait
class TemperatureSettingTrait(_Trait):
    """Trait to offer handling both temperature point and modes functionality.

    https://developers.google.com/actions/smarthome/traits/temperaturesetting
    """

    name = TRAIT_TEMPERATURE_SETTING
    commands = [
        COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT,
        COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE,
        COMMAND_THERMOSTAT_SET_MODE,
    ]
    # We do not support "on" as we are unable to know how to restore
    # the last mode.
    hvac_to_google = {
        climate.HVAC_MODE_HEAT: "heat",
        climate.HVAC_MODE_COOL: "cool",
        climate.HVAC_MODE_OFF: "off",
        climate.HVAC_MODE_AUTO: "auto",
        climate.HVAC_MODE_HEAT_COOL: "heatcool",
        climate.HVAC_MODE_FAN_ONLY: "fan-only",
        climate.HVAC_MODE_DRY: "dry",
    }
    google_to_hvac = {value: key for key, value in hvac_to_google.items()}

    preset_to_google = {climate.PRESET_ECO: "eco"}
    google_to_preset = {value: key for key, value in preset_to_google.items()}

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == climate.DOMAIN:
            return True

        return (
            domain == sensor.DOMAIN and device_class == sensor.DEVICE_CLASS_TEMPERATURE
        )

    @property
    def climate_google_modes(self):
        """Return supported Google modes."""
        modes = []
        attrs = self.state.attributes

        for mode in attrs.get(climate.ATTR_HVAC_MODES, []):
            google_mode = self.hvac_to_google.get(mode)
            if google_mode and google_mode not in modes:
                modes.append(google_mode)

        for preset in attrs.get(climate.ATTR_PRESET_MODES, []):
            google_mode = self.preset_to_google.get(preset)
            if google_mode and google_mode not in modes:
                modes.append(google_mode)

        return modes

    def sync_attributes(self):
        """Return temperature point and modes attributes for a sync request."""
        response = {}
        attrs = self.state.attributes
        domain = self.state.domain
        response["thermostatTemperatureUnit"] = _google_temp_unit(
            self.hass.config.units.temperature_unit
        )

        if domain == sensor.DOMAIN:
            device_class = attrs.get(ATTR_DEVICE_CLASS)
            if device_class == sensor.DEVICE_CLASS_TEMPERATURE:
                response["queryOnlyTemperatureSetting"] = True

        elif domain == climate.DOMAIN:
            modes = self.climate_google_modes

            # Some integrations don't support modes (e.g. opentherm), but Google doesn't
            # support changing the temperature if we don't have any modes. If there's
            # only one Google doesn't support changing it, so the default mode here is
            # only cosmetic.
            if len(modes) == 0:
                modes.append("heat")

            if "off" in modes and any(
                mode in modes for mode in ("heatcool", "heat", "cool")
            ):
                modes.append("on")
            response["availableThermostatModes"] = ",".join(modes)

        return response

    def query_attributes(self):
        """Return temperature point and modes query attributes."""
        response = {}
        attrs = self.state.attributes
        domain = self.state.domain
        unit = self.hass.config.units.temperature_unit
        if domain == sensor.DOMAIN:
            device_class = attrs.get(ATTR_DEVICE_CLASS)
            if device_class == sensor.DEVICE_CLASS_TEMPERATURE:
                current_temp = self.state.state
                if current_temp not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    response["thermostatTemperatureAmbient"] = round(
                        temp_util.convert(float(current_temp), unit, TEMP_CELSIUS), 1
                    )

        elif domain == climate.DOMAIN:
            operation = self.state.state
            preset = attrs.get(climate.ATTR_PRESET_MODE)
            supported = attrs.get(ATTR_SUPPORTED_FEATURES, 0)

            if preset in self.preset_to_google:
                response["thermostatMode"] = self.preset_to_google[preset]
            else:
                response["thermostatMode"] = self.hvac_to_google.get(operation)

            current_temp = attrs.get(climate.ATTR_CURRENT_TEMPERATURE)
            if current_temp is not None:
                response["thermostatTemperatureAmbient"] = round(
                    temp_util.convert(current_temp, unit, TEMP_CELSIUS), 1
                )

            current_humidity = attrs.get(climate.ATTR_CURRENT_HUMIDITY)
            if current_humidity is not None:
                response["thermostatHumidityAmbient"] = current_humidity

            if operation in (climate.HVAC_MODE_AUTO, climate.HVAC_MODE_HEAT_COOL):
                if supported & climate.SUPPORT_TARGET_TEMPERATURE_RANGE:
                    response["thermostatTemperatureSetpointHigh"] = round(
                        temp_util.convert(
                            attrs[climate.ATTR_TARGET_TEMP_HIGH], unit, TEMP_CELSIUS
                        ),
                        1,
                    )
                    response["thermostatTemperatureSetpointLow"] = round(
                        temp_util.convert(
                            attrs[climate.ATTR_TARGET_TEMP_LOW], unit, TEMP_CELSIUS
                        ),
                        1,
                    )
                else:
                    target_temp = attrs.get(ATTR_TEMPERATURE)
                    if target_temp is not None:
                        target_temp = round(
                            temp_util.convert(target_temp, unit, TEMP_CELSIUS), 1
                        )
                        response["thermostatTemperatureSetpointHigh"] = target_temp
                        response["thermostatTemperatureSetpointLow"] = target_temp
            else:
                target_temp = attrs.get(ATTR_TEMPERATURE)
                if target_temp is not None:
                    response["thermostatTemperatureSetpoint"] = round(
                        temp_util.convert(target_temp, unit, TEMP_CELSIUS), 1
                    )

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a temperature point or mode command."""
        domain = self.state.domain
        if domain == sensor.DOMAIN:
            raise SmartHomeError(
                ERR_NOT_SUPPORTED, "Execute is not supported by sensor"
            )

        # All sent in temperatures are always in Celsius
        unit = self.hass.config.units.temperature_unit
        min_temp = self.state.attributes[climate.ATTR_MIN_TEMP]
        max_temp = self.state.attributes[climate.ATTR_MAX_TEMP]

        if command == COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT:
            temp = temp_util.convert(
                params["thermostatTemperatureSetpoint"], TEMP_CELSIUS, unit
            )
            if unit == TEMP_FAHRENHEIT:
                temp = round(temp)

            if temp < min_temp or temp > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    f"Temperature should be between {min_temp} and {max_temp}",
                )

            await self.hass.services.async_call(
                climate.DOMAIN,
                climate.SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: self.state.entity_id, ATTR_TEMPERATURE: temp},
                blocking=True,
                context=data.context,
            )

        elif command == COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE:
            temp_high = temp_util.convert(
                params["thermostatTemperatureSetpointHigh"], TEMP_CELSIUS, unit
            )
            if unit == TEMP_FAHRENHEIT:
                temp_high = round(temp_high)

            if temp_high < min_temp or temp_high > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    (
                        f"Upper bound for temperature range should be between "
                        f"{min_temp} and {max_temp}"
                    ),
                )

            temp_low = temp_util.convert(
                params["thermostatTemperatureSetpointLow"], TEMP_CELSIUS, unit
            )
            if unit == TEMP_FAHRENHEIT:
                temp_low = round(temp_low)

            if temp_low < min_temp or temp_low > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    (
                        f"Lower bound for temperature range should be between "
                        f"{min_temp} and {max_temp}"
                    ),
                )

            supported = self.state.attributes.get(ATTR_SUPPORTED_FEATURES)
            svc_data = {ATTR_ENTITY_ID: self.state.entity_id}

            if supported & climate.SUPPORT_TARGET_TEMPERATURE_RANGE:
                svc_data[climate.ATTR_TARGET_TEMP_HIGH] = temp_high
                svc_data[climate.ATTR_TARGET_TEMP_LOW] = temp_low
            else:
                svc_data[ATTR_TEMPERATURE] = (temp_high + temp_low) / 2

            await self.hass.services.async_call(
                climate.DOMAIN,
                climate.SERVICE_SET_TEMPERATURE,
                svc_data,
                blocking=True,
                context=data.context,
            )

        elif command == COMMAND_THERMOSTAT_SET_MODE:
            target_mode = params["thermostatMode"]
            supported = self.state.attributes.get(ATTR_SUPPORTED_FEATURES)

            if target_mode == "on":
                await self.hass.services.async_call(
                    climate.DOMAIN,
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=True,
                    context=data.context,
                )
                return

            if target_mode == "off":
                await self.hass.services.async_call(
                    climate.DOMAIN,
                    SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=True,
                    context=data.context,
                )
                return

            if target_mode in self.google_to_preset:
                await self.hass.services.async_call(
                    climate.DOMAIN,
                    climate.SERVICE_SET_PRESET_MODE,
                    {
                        climate.ATTR_PRESET_MODE: self.google_to_preset[target_mode],
                        ATTR_ENTITY_ID: self.state.entity_id,
                    },
                    blocking=True,
                    context=data.context,
                )
                return

            await self.hass.services.async_call(
                climate.DOMAIN,
                climate.SERVICE_SET_HVAC_MODE,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    climate.ATTR_HVAC_MODE: self.google_to_hvac[target_mode],
                },
                blocking=True,
                context=data.context,
            )


@register_trait
class HumiditySettingTrait(_Trait):
    """Trait to offer humidity setting functionality.

    https://developers.google.com/actions/smarthome/traits/humiditysetting
    """

    name = TRAIT_HUMIDITY_SETTING
    commands = [COMMAND_SET_HUMIDITY]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == humidifier.DOMAIN:
            return True

        return domain == sensor.DOMAIN and device_class == sensor.DEVICE_CLASS_HUMIDITY

    def sync_attributes(self):
        """Return humidity attributes for a sync request."""
        response = {}
        attrs = self.state.attributes
        domain = self.state.domain

        if domain == sensor.DOMAIN:
            device_class = attrs.get(ATTR_DEVICE_CLASS)
            if device_class == sensor.DEVICE_CLASS_HUMIDITY:
                response["queryOnlyHumiditySetting"] = True

        elif domain == humidifier.DOMAIN:
            response["humiditySetpointRange"] = {
                "minPercent": round(
                    float(self.state.attributes[humidifier.ATTR_MIN_HUMIDITY])
                ),
                "maxPercent": round(
                    float(self.state.attributes[humidifier.ATTR_MAX_HUMIDITY])
                ),
            }

        return response

    def query_attributes(self):
        """Return humidity query attributes."""
        response = {}
        attrs = self.state.attributes
        domain = self.state.domain

        if domain == sensor.DOMAIN:
            device_class = attrs.get(ATTR_DEVICE_CLASS)
            if device_class == sensor.DEVICE_CLASS_HUMIDITY:
                current_humidity = self.state.state
                if current_humidity not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    response["humidityAmbientPercent"] = round(float(current_humidity))

        elif domain == humidifier.DOMAIN:
            target_humidity = attrs.get(humidifier.ATTR_HUMIDITY)
            if target_humidity is not None:
                response["humiditySetpointPercent"] = round(float(target_humidity))

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a humidity command."""
        domain = self.state.domain

        if domain == sensor.DOMAIN:
            raise SmartHomeError(
                ERR_NOT_SUPPORTED, "Execute is not supported by sensor"
            )

        if command == COMMAND_SET_HUMIDITY:
            await self.hass.services.async_call(
                humidifier.DOMAIN,
                humidifier.SERVICE_SET_HUMIDITY,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    humidifier.ATTR_HUMIDITY: params["humidity"],
                },
                blocking=True,
                context=data.context,
            )


@register_trait
class LockUnlockTrait(_Trait):
    """Trait to lock or unlock a lock.

    https://developers.google.com/actions/smarthome/traits/lockunlock
    """

    name = TRAIT_LOCKUNLOCK
    commands = [COMMAND_LOCKUNLOCK]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        return domain == lock.DOMAIN

    @staticmethod
    def might_2fa(domain, features, device_class):
        """Return if the trait might ask for 2FA."""
        return True

    def sync_attributes(self):
        """Return LockUnlock attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return LockUnlock query attributes."""
        return {"isLocked": self.state.state == STATE_LOCKED}

    async def execute(self, command, data, params, challenge):
        """Execute an LockUnlock command."""
        if params["lock"]:
            service = lock.SERVICE_LOCK
        else:
            _verify_pin_challenge(data, self.state, challenge)
            service = lock.SERVICE_UNLOCK

        await self.hass.services.async_call(
            lock.DOMAIN,
            service,
            {ATTR_ENTITY_ID: self.state.entity_id},
            blocking=True,
            context=data.context,
        )


@register_trait
class ArmDisArmTrait(_Trait):
    """Trait to Arm or Disarm a Security System.

    https://developers.google.com/actions/smarthome/traits/armdisarm
    """

    name = TRAIT_ARMDISARM
    commands = [COMMAND_ARMDISARM]

    state_to_service = {
        STATE_ALARM_ARMED_HOME: SERVICE_ALARM_ARM_HOME,
        STATE_ALARM_ARMED_AWAY: SERVICE_ALARM_ARM_AWAY,
        STATE_ALARM_ARMED_NIGHT: SERVICE_ALARM_ARM_NIGHT,
        STATE_ALARM_ARMED_CUSTOM_BYPASS: SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        STATE_ALARM_TRIGGERED: SERVICE_ALARM_TRIGGER,
    }

    state_to_support = {
        STATE_ALARM_ARMED_HOME: alarm_control_panel.const.SUPPORT_ALARM_ARM_HOME,
        STATE_ALARM_ARMED_AWAY: alarm_control_panel.const.SUPPORT_ALARM_ARM_AWAY,
        STATE_ALARM_ARMED_NIGHT: alarm_control_panel.const.SUPPORT_ALARM_ARM_NIGHT,
        STATE_ALARM_ARMED_CUSTOM_BYPASS: alarm_control_panel.const.SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
        STATE_ALARM_TRIGGERED: alarm_control_panel.const.SUPPORT_ALARM_TRIGGER,
    }

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        return domain == alarm_control_panel.DOMAIN

    @staticmethod
    def might_2fa(domain, features, device_class):
        """Return if the trait might ask for 2FA."""
        return True

    def _supported_states(self):
        """Return supported states."""
        features = self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        return [
            state
            for state, required_feature in self.state_to_support.items()
            if features & required_feature != 0
        ]

    def sync_attributes(self):
        """Return ArmDisarm attributes for a sync request."""
        response = {}
        levels = []
        for state in self._supported_states():
            # level synonyms are generated from state names
            # 'armed_away' becomes 'armed away' or 'away'
            level_synonym = [state.replace("_", " ")]
            if state != STATE_ALARM_TRIGGERED:
                level_synonym.append(state.split("_")[1])

            level = {
                "level_name": state,
                "level_values": [{"level_synonym": level_synonym, "lang": "en"}],
            }
            levels.append(level)

        response["availableArmLevels"] = {"levels": levels, "ordered": False}
        return response

    def query_attributes(self):
        """Return ArmDisarm query attributes."""
        if "next_state" in self.state.attributes:
            armed_state = self.state.attributes["next_state"]
        else:
            armed_state = self.state.state
        response = {"isArmed": armed_state in self.state_to_service}
        if response["isArmed"]:
            response.update({"currentArmLevel": armed_state})
        return response

    async def execute(self, command, data, params, challenge):
        """Execute an ArmDisarm command."""
        if params["arm"] and not params.get("cancel"):
            arm_level = params.get("armLevel")

            # If no arm level given, we can only arm it if there is
            # only one supported arm type. We never default to triggered.
            if not arm_level:
                states = self._supported_states()

                if STATE_ALARM_TRIGGERED in states:
                    states.remove(STATE_ALARM_TRIGGERED)

                if len(states) != 1:
                    raise SmartHomeError(ERR_NOT_SUPPORTED, "ArmLevel missing")

                arm_level = states[0]

            if self.state.state == arm_level:
                raise SmartHomeError(ERR_ALREADY_ARMED, "System is already armed")
            if self.state.attributes["code_arm_required"]:
                _verify_pin_challenge(data, self.state, challenge)
            service = self.state_to_service[arm_level]
        # disarm the system without asking for code when
        # 'cancel' arming action is received while current status is pending
        elif (
            params["arm"]
            and params.get("cancel")
            and self.state.state == STATE_ALARM_PENDING
        ):
            service = SERVICE_ALARM_DISARM
        else:
            if self.state.state == STATE_ALARM_DISARMED:
                raise SmartHomeError(ERR_ALREADY_DISARMED, "System is already disarmed")
            _verify_pin_challenge(data, self.state, challenge)
            service = SERVICE_ALARM_DISARM

        await self.hass.services.async_call(
            alarm_control_panel.DOMAIN,
            service,
            {
                ATTR_ENTITY_ID: self.state.entity_id,
                ATTR_CODE: data.config.secure_devices_pin,
            },
            blocking=True,
            context=data.context,
        )


@register_trait
class FanSpeedTrait(_Trait):
    """Trait to control speed of Fan.

    https://developers.google.com/actions/smarthome/traits/fanspeed
    """

    name = TRAIT_FANSPEED
    commands = [COMMAND_FANSPEED]

    speed_synonyms = {
        fan.SPEED_OFF: ["stop", "off"],
        fan.SPEED_LOW: ["slow", "low", "slowest", "lowest"],
        fan.SPEED_MEDIUM: ["medium", "mid", "middle"],
        fan.SPEED_HIGH: ["high", "max", "fast", "highest", "fastest", "maximum"],
    }

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == fan.DOMAIN:
            return features & fan.SUPPORT_SET_SPEED
        if domain == climate.DOMAIN:
            return features & climate.SUPPORT_FAN_MODE
        return False

    def sync_attributes(self):
        """Return speed point and modes attributes for a sync request."""
        domain = self.state.domain
        speeds = []
        reversible = False

        if domain == fan.DOMAIN:
            modes = self.state.attributes.get(fan.ATTR_SPEED_LIST, [])
            for mode in modes:
                if mode not in self.speed_synonyms:
                    continue
                speed = {
                    "speed_name": mode,
                    "speed_values": [
                        {"speed_synonym": self.speed_synonyms.get(mode), "lang": "en"}
                    ],
                }
                speeds.append(speed)
            reversible = bool(
                self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
                & fan.SUPPORT_DIRECTION
            )
        elif domain == climate.DOMAIN:
            modes = self.state.attributes.get(climate.ATTR_FAN_MODES, [])
            for mode in modes:
                speed = {
                    "speed_name": mode,
                    "speed_values": [{"speed_synonym": [mode], "lang": "en"}],
                }
                speeds.append(speed)

        return {
            "availableFanSpeeds": {"speeds": speeds, "ordered": True},
            "reversible": reversible,
        }

    def query_attributes(self):
        """Return speed point and modes query attributes."""
        attrs = self.state.attributes
        domain = self.state.domain
        response = {}
        if domain == climate.DOMAIN:
            speed = attrs.get(climate.ATTR_FAN_MODE)
            if speed is not None:
                response["currentFanSpeedSetting"] = speed
        if domain == fan.DOMAIN:
            speed = attrs.get(fan.ATTR_SPEED)
            if speed is not None:
                response["on"] = speed != fan.SPEED_OFF
                response["currentFanSpeedSetting"] = speed
        return response

    async def execute(self, command, data, params, challenge):
        """Execute an SetFanSpeed command."""
        domain = self.state.domain
        if domain == climate.DOMAIN:
            await self.hass.services.async_call(
                climate.DOMAIN,
                climate.SERVICE_SET_FAN_MODE,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    climate.ATTR_FAN_MODE: params["fanSpeed"],
                },
                blocking=True,
                context=data.context,
            )
        if domain == fan.DOMAIN:
            await self.hass.services.async_call(
                fan.DOMAIN,
                fan.SERVICE_SET_SPEED,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    fan.ATTR_SPEED: params["fanSpeed"],
                },
                blocking=True,
                context=data.context,
            )


@register_trait
class ModesTrait(_Trait):
    """Trait to set modes.

    https://developers.google.com/actions/smarthome/traits/modes
    """

    name = TRAIT_MODES
    commands = [COMMAND_MODES]

    SYNONYMS = {
        "sound mode": ["sound mode", "effects"],
        "option": ["option", "setting", "mode", "value"],
    }

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == input_select.DOMAIN:
            return True

        if domain == humidifier.DOMAIN and features & humidifier.SUPPORT_MODES:
            return True

        if domain != media_player.DOMAIN:
            return False

        return features & media_player.SUPPORT_SELECT_SOUND_MODE

    def _generate(self, name, settings):
        """Generate a list of modes."""
        mode = {
            "name": name,
            "name_values": [
                {"name_synonym": self.SYNONYMS.get(name, [name]), "lang": "en"}
            ],
            "settings": [],
            "ordered": False,
        }
        for setting in settings:
            mode["settings"].append(
                {
                    "setting_name": setting,
                    "setting_values": [
                        {
                            "setting_synonym": self.SYNONYMS.get(setting, [setting]),
                            "lang": "en",
                        }
                    ],
                }
            )
        return mode

    def sync_attributes(self):
        """Return mode attributes for a sync request."""
        modes = []

        for domain, attr, name in (
            (media_player.DOMAIN, media_player.ATTR_SOUND_MODE_LIST, "sound mode"),
            (input_select.DOMAIN, input_select.ATTR_OPTIONS, "option"),
            (humidifier.DOMAIN, humidifier.ATTR_AVAILABLE_MODES, "mode"),
        ):
            if self.state.domain != domain:
                continue

            items = self.state.attributes.get(attr)

            if items is not None:
                modes.append(self._generate(name, items))

            # Shortcut since all domains are currently unique
            break

        payload = {"availableModes": modes}

        return payload

    def query_attributes(self):
        """Return current modes."""
        attrs = self.state.attributes
        response = {}
        mode_settings = {}

        if self.state.domain == media_player.DOMAIN:
            if media_player.ATTR_SOUND_MODE_LIST in attrs:
                mode_settings["sound mode"] = attrs.get(media_player.ATTR_SOUND_MODE)
        elif self.state.domain == input_select.DOMAIN:
            mode_settings["option"] = self.state.state
        elif self.state.domain == humidifier.DOMAIN:
            if humidifier.ATTR_MODE in attrs:
                mode_settings["mode"] = attrs.get(humidifier.ATTR_MODE)

        if mode_settings:
            response["on"] = self.state.state not in (STATE_OFF, STATE_UNKNOWN)
            response["currentModeSettings"] = mode_settings

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a SetModes command."""
        settings = params.get("updateModeSettings")

        if self.state.domain == input_select.DOMAIN:
            option = params["updateModeSettings"]["option"]
            await self.hass.services.async_call(
                input_select.DOMAIN,
                input_select.SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    input_select.ATTR_OPTION: option,
                },
                blocking=True,
                context=data.context,
            )
            return

        if self.state.domain == humidifier.DOMAIN:
            requested_mode = settings["mode"]
            await self.hass.services.async_call(
                humidifier.DOMAIN,
                humidifier.SERVICE_SET_MODE,
                {
                    humidifier.ATTR_MODE: requested_mode,
                    ATTR_ENTITY_ID: self.state.entity_id,
                },
                blocking=True,
                context=data.context,
            )
            return

        if self.state.domain != media_player.DOMAIN:
            _LOGGER.info(
                "Received an Options command for unrecognised domain %s",
                self.state.domain,
            )
            return

        sound_mode = settings.get("sound mode")

        if sound_mode:
            await self.hass.services.async_call(
                media_player.DOMAIN,
                media_player.SERVICE_SELECT_SOUND_MODE,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    media_player.ATTR_SOUND_MODE: sound_mode,
                },
                blocking=True,
                context=data.context,
            )


@register_trait
class InputSelectorTrait(_Trait):
    """Trait to set modes.

    https://developers.google.com/assistant/smarthome/traits/inputselector
    """

    name = TRAIT_INPUTSELECTOR
    commands = [COMMAND_INPUT, COMMAND_NEXT_INPUT, COMMAND_PREVIOUS_INPUT]

    SYNONYMS = {}

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == media_player.DOMAIN and (
            features & media_player.SUPPORT_SELECT_SOURCE
        ):
            return True

        return False

    def sync_attributes(self):
        """Return mode attributes for a sync request."""
        attrs = self.state.attributes
        inputs = [
            {"key": source, "names": [{"name_synonym": [source], "lang": "en"}]}
            for source in attrs.get(media_player.ATTR_INPUT_SOURCE_LIST, [])
        ]

        payload = {"availableInputs": inputs, "orderedInputs": True}

        return payload

    def query_attributes(self):
        """Return current modes."""
        attrs = self.state.attributes
        return {"currentInput": attrs.get(media_player.ATTR_INPUT_SOURCE, "")}

    async def execute(self, command, data, params, challenge):
        """Execute an SetInputSource command."""
        sources = self.state.attributes.get(media_player.ATTR_INPUT_SOURCE_LIST) or []
        source = self.state.attributes.get(media_player.ATTR_INPUT_SOURCE)

        if command == COMMAND_INPUT:
            requested_source = params.get("newInput")
        elif command == COMMAND_NEXT_INPUT:
            requested_source = _next_selected(sources, source)
        elif command == COMMAND_PREVIOUS_INPUT:
            requested_source = _next_selected(list(reversed(sources)), source)
        else:
            raise SmartHomeError(ERR_NOT_SUPPORTED, "Unsupported command")

        if requested_source not in sources:
            raise SmartHomeError(ERR_UNSUPPORTED_INPUT, "Unsupported input")

        await self.hass.services.async_call(
            media_player.DOMAIN,
            media_player.SERVICE_SELECT_SOURCE,
            {
                ATTR_ENTITY_ID: self.state.entity_id,
                media_player.ATTR_INPUT_SOURCE: requested_source,
            },
            blocking=True,
            context=data.context,
        )


@register_trait
class OpenCloseTrait(_Trait):
    """Trait to open and close a cover.

    https://developers.google.com/actions/smarthome/traits/openclose
    """

    # Cover device classes that require 2FA
    COVER_2FA = (
        cover.DEVICE_CLASS_DOOR,
        cover.DEVICE_CLASS_GARAGE,
        cover.DEVICE_CLASS_GATE,
    )

    name = TRAIT_OPENCLOSE
    commands = [COMMAND_OPENCLOSE]

    override_position = None

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == cover.DOMAIN:
            return True

        return domain == binary_sensor.DOMAIN and device_class in (
            binary_sensor.DEVICE_CLASS_DOOR,
            binary_sensor.DEVICE_CLASS_GARAGE_DOOR,
            binary_sensor.DEVICE_CLASS_LOCK,
            binary_sensor.DEVICE_CLASS_OPENING,
            binary_sensor.DEVICE_CLASS_WINDOW,
        )

    @staticmethod
    def might_2fa(domain, features, device_class):
        """Return if the trait might ask for 2FA."""
        return domain == cover.DOMAIN and device_class in OpenCloseTrait.COVER_2FA

    def sync_attributes(self):
        """Return opening direction."""
        response = {}
        if self.state.domain == binary_sensor.DOMAIN:
            response["queryOnlyOpenClose"] = True
        return response

    def query_attributes(self):
        """Return state query attributes."""
        domain = self.state.domain
        response = {}

        if self.override_position is not None:
            response["openPercent"] = self.override_position

        elif domain == cover.DOMAIN:
            # When it's an assumed state, we will return that querying state
            # is not supported.
            if self.state.attributes.get(ATTR_ASSUMED_STATE):
                raise SmartHomeError(
                    ERR_NOT_SUPPORTED, "Querying state is not supported"
                )

            if self.state.state == STATE_UNKNOWN:
                raise SmartHomeError(
                    ERR_NOT_SUPPORTED, "Querying state is not supported"
                )

            position = self.override_position or self.state.attributes.get(
                cover.ATTR_CURRENT_POSITION
            )

            if position is not None:
                response["openPercent"] = position
            elif self.state.state != cover.STATE_CLOSED:
                response["openPercent"] = 100
            else:
                response["openPercent"] = 0

        elif domain == binary_sensor.DOMAIN:
            if self.state.state == STATE_ON:
                response["openPercent"] = 100
            else:
                response["openPercent"] = 0

        return response

    async def execute(self, command, data, params, challenge):
        """Execute an Open, close, Set position command."""
        domain = self.state.domain

        if domain == cover.DOMAIN:
            svc_params = {ATTR_ENTITY_ID: self.state.entity_id}

            if params["openPercent"] == 0:
                service = cover.SERVICE_CLOSE_COVER
                should_verify = False
            elif params["openPercent"] == 100:
                service = cover.SERVICE_OPEN_COVER
                should_verify = True
            elif (
                self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
                & cover.SUPPORT_SET_POSITION
            ):
                service = cover.SERVICE_SET_COVER_POSITION
                should_verify = True
                svc_params[cover.ATTR_POSITION] = params["openPercent"]
            else:
                raise SmartHomeError(
                    ERR_FUNCTION_NOT_SUPPORTED, "Setting a position is not supported"
                )

            if (
                should_verify
                and self.state.attributes.get(ATTR_DEVICE_CLASS)
                in OpenCloseTrait.COVER_2FA
            ):
                _verify_pin_challenge(data, self.state, challenge)

            await self.hass.services.async_call(
                cover.DOMAIN, service, svc_params, blocking=True, context=data.context
            )

            if (
                self.state.attributes.get(ATTR_ASSUMED_STATE)
                or self.state.state == STATE_UNKNOWN
            ):
                self.override_position = params["openPercent"]


@register_trait
class VolumeTrait(_Trait):
    """Trait to control brightness of a device.

    https://developers.google.com/actions/smarthome/traits/volume
    """

    name = TRAIT_VOLUME
    commands = [COMMAND_SET_VOLUME, COMMAND_VOLUME_RELATIVE]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == media_player.DOMAIN:
            return features & media_player.SUPPORT_VOLUME_SET

        return False

    def sync_attributes(self):
        """Return brightness attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return brightness query attributes."""
        response = {}

        level = self.state.attributes.get(media_player.ATTR_MEDIA_VOLUME_LEVEL)
        muted = self.state.attributes.get(media_player.ATTR_MEDIA_VOLUME_MUTED)
        if level is not None:
            # Convert 0.0-1.0 to 0-100
            response["currentVolume"] = int(level * 100)
            response["isMuted"] = bool(muted)

        return response

    async def _execute_set_volume(self, data, params):
        level = params["volumeLevel"]

        await self.hass.services.async_call(
            media_player.DOMAIN,
            media_player.SERVICE_VOLUME_SET,
            {
                ATTR_ENTITY_ID: self.state.entity_id,
                media_player.ATTR_MEDIA_VOLUME_LEVEL: level / 100,
            },
            blocking=True,
            context=data.context,
        )

    async def _execute_volume_relative(self, data, params):
        # This could also support up/down commands using relativeSteps
        relative = params["volumeRelativeLevel"]
        current = self.state.attributes.get(media_player.ATTR_MEDIA_VOLUME_LEVEL)

        await self.hass.services.async_call(
            media_player.DOMAIN,
            media_player.SERVICE_VOLUME_SET,
            {
                ATTR_ENTITY_ID: self.state.entity_id,
                media_player.ATTR_MEDIA_VOLUME_LEVEL: current + relative / 100,
            },
            blocking=True,
            context=data.context,
        )

    async def execute(self, command, data, params, challenge):
        """Execute a brightness command."""
        if command == COMMAND_SET_VOLUME:
            await self._execute_set_volume(data, params)
        elif command == COMMAND_VOLUME_RELATIVE:
            await self._execute_volume_relative(data, params)
        else:
            raise SmartHomeError(ERR_NOT_SUPPORTED, "Command not supported")


def _verify_pin_challenge(data, state, challenge):
    """Verify a pin challenge."""
    if not data.config.should_2fa(state):
        return
    if not data.config.secure_devices_pin:
        raise SmartHomeError(ERR_CHALLENGE_NOT_SETUP, "Challenge is not set up")

    if not challenge:
        raise ChallengeNeeded(CHALLENGE_PIN_NEEDED)

    pin = challenge.get("pin")

    if pin != data.config.secure_devices_pin:
        raise ChallengeNeeded(CHALLENGE_FAILED_PIN_NEEDED)


def _verify_ack_challenge(data, state, challenge):
    """Verify an ack challenge."""
    if not data.config.should_2fa(state):
        return
    if not challenge or not challenge.get("ack"):
        raise ChallengeNeeded(CHALLENGE_ACK_NEEDED)


MEDIA_COMMAND_SUPPORT_MAPPING = {
    COMMAND_MEDIA_NEXT: media_player.SUPPORT_NEXT_TRACK,
    COMMAND_MEDIA_PAUSE: media_player.SUPPORT_PAUSE,
    COMMAND_MEDIA_PREVIOUS: media_player.SUPPORT_PREVIOUS_TRACK,
    COMMAND_MEDIA_RESUME: media_player.SUPPORT_PLAY,
    COMMAND_MEDIA_SEEK_RELATIVE: media_player.SUPPORT_SEEK,
    COMMAND_MEDIA_SEEK_TO_POSITION: media_player.SUPPORT_SEEK,
    COMMAND_MEDIA_SHUFFLE: media_player.SUPPORT_SHUFFLE_SET,
    COMMAND_MEDIA_STOP: media_player.SUPPORT_STOP,
}

MEDIA_COMMAND_ATTRIBUTES = {
    COMMAND_MEDIA_NEXT: "NEXT",
    COMMAND_MEDIA_PAUSE: "PAUSE",
    COMMAND_MEDIA_PREVIOUS: "PREVIOUS",
    COMMAND_MEDIA_RESUME: "RESUME",
    COMMAND_MEDIA_SEEK_RELATIVE: "SEEK_RELATIVE",
    COMMAND_MEDIA_SEEK_TO_POSITION: "SEEK_TO_POSITION",
    COMMAND_MEDIA_SHUFFLE: "SHUFFLE",
    COMMAND_MEDIA_STOP: "STOP",
}


@register_trait
class TransportControlTrait(_Trait):
    """Trait to control media playback.

    https://developers.google.com/actions/smarthome/traits/transportcontrol
    """

    name = TRAIT_TRANSPORT_CONTROL
    commands = [
        COMMAND_MEDIA_NEXT,
        COMMAND_MEDIA_PAUSE,
        COMMAND_MEDIA_PREVIOUS,
        COMMAND_MEDIA_RESUME,
        COMMAND_MEDIA_SEEK_RELATIVE,
        COMMAND_MEDIA_SEEK_TO_POSITION,
        COMMAND_MEDIA_SHUFFLE,
        COMMAND_MEDIA_STOP,
    ]

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain == media_player.DOMAIN:
            for feature in MEDIA_COMMAND_SUPPORT_MAPPING.values():
                if features & feature:
                    return True

        return False

    def sync_attributes(self):
        """Return opening direction."""
        response = {}

        if self.state.domain == media_player.DOMAIN:
            features = self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

            support = []
            for command, feature in MEDIA_COMMAND_SUPPORT_MAPPING.items():
                if features & feature:
                    support.append(MEDIA_COMMAND_ATTRIBUTES[command])
            response["transportControlSupportedCommands"] = support

        return response

    def query_attributes(self):
        """Return the attributes of this trait for this entity."""

        return {}

    async def execute(self, command, data, params, challenge):
        """Execute a media command."""

        service_attrs = {ATTR_ENTITY_ID: self.state.entity_id}

        if command == COMMAND_MEDIA_SEEK_RELATIVE:
            service = media_player.SERVICE_MEDIA_SEEK

            rel_position = params["relativePositionMs"] / 1000
            seconds_since = 0  # Default to 0 seconds
            if self.state.state == STATE_PLAYING:
                now = dt.utcnow()
                upd_at = self.state.attributes.get(
                    media_player.ATTR_MEDIA_POSITION_UPDATED_AT, now
                )
                seconds_since = (now - upd_at).total_seconds()
            position = self.state.attributes.get(media_player.ATTR_MEDIA_POSITION, 0)
            max_position = self.state.attributes.get(
                media_player.ATTR_MEDIA_DURATION, 0
            )
            service_attrs[media_player.ATTR_MEDIA_SEEK_POSITION] = min(
                max(position + seconds_since + rel_position, 0), max_position
            )
        elif command == COMMAND_MEDIA_SEEK_TO_POSITION:
            service = media_player.SERVICE_MEDIA_SEEK

            max_position = self.state.attributes.get(
                media_player.ATTR_MEDIA_DURATION, 0
            )
            service_attrs[media_player.ATTR_MEDIA_SEEK_POSITION] = min(
                max(params["absPositionMs"] / 1000, 0), max_position
            )
        elif command == COMMAND_MEDIA_NEXT:
            service = media_player.SERVICE_MEDIA_NEXT_TRACK
        elif command == COMMAND_MEDIA_PAUSE:
            service = media_player.SERVICE_MEDIA_PAUSE
        elif command == COMMAND_MEDIA_PREVIOUS:
            service = media_player.SERVICE_MEDIA_PREVIOUS_TRACK
        elif command == COMMAND_MEDIA_RESUME:
            service = media_player.SERVICE_MEDIA_PLAY
        elif command == COMMAND_MEDIA_SHUFFLE:
            service = media_player.SERVICE_SHUFFLE_SET

            # Google Assistant only supports enabling shuffle
            service_attrs[media_player.ATTR_MEDIA_SHUFFLE] = True
        elif command == COMMAND_MEDIA_STOP:
            service = media_player.SERVICE_MEDIA_STOP
        else:
            raise SmartHomeError(ERR_NOT_SUPPORTED, "Command not supported")

        await self.hass.services.async_call(
            media_player.DOMAIN,
            service,
            service_attrs,
            blocking=True,
            context=data.context,
        )


@register_trait
class MediaStateTrait(_Trait):
    """Trait to get media playback state.

    https://developers.google.com/actions/smarthome/traits/mediastate
    """

    name = TRAIT_MEDIA_STATE
    commands = []

    activity_lookup = {
        STATE_OFF: "INACTIVE",
        STATE_IDLE: "STANDBY",
        STATE_PLAYING: "ACTIVE",
        STATE_ON: "STANDBY",
        STATE_PAUSED: "STANDBY",
        STATE_STANDBY: "STANDBY",
        STATE_UNAVAILABLE: "INACTIVE",
        STATE_UNKNOWN: "INACTIVE",
    }

    playback_lookup = {
        STATE_OFF: "STOPPED",
        STATE_IDLE: "STOPPED",
        STATE_PLAYING: "PLAYING",
        STATE_ON: "STOPPED",
        STATE_PAUSED: "PAUSED",
        STATE_STANDBY: "STOPPED",
        STATE_UNAVAILABLE: "STOPPED",
        STATE_UNKNOWN: "STOPPED",
    }

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        return domain == media_player.DOMAIN

    def sync_attributes(self):
        """Return attributes for a sync request."""
        return {"supportActivityState": True, "supportPlaybackState": True}

    def query_attributes(self):
        """Return the attributes of this trait for this entity."""
        return {
            "activityState": self.activity_lookup.get(self.state.state, "INACTIVE"),
            "playbackState": self.playback_lookup.get(self.state.state, "STOPPED"),
        }
