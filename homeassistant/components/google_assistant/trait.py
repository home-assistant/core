"""Implement the Google Smart Home traits."""
import logging

from homeassistant.components import (
    alarm_control_panel,
    binary_sensor,
    camera,
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
    vacuum,
)
from homeassistant.components.climate import const as climate
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
    STATE_LOCKED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import DOMAIN as HA_DOMAIN
from homeassistant.helpers.network import async_get_url
from homeassistant.util import color as color_util, temperature as temp_util

from .const import (
    CHALLENGE_ACK_NEEDED,
    CHALLENGE_FAILED_PIN_NEEDED,
    CHALLENGE_PIN_NEEDED,
    ERR_ALREADY_ARMED,
    ERR_ALREADY_DISARMED,
    ERR_CHALLENGE_NOT_SETUP,
    ERR_FUNCTION_NOT_SUPPORTED,
    ERR_NOT_SUPPORTED,
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
TRAIT_OPENCLOSE = f"{PREFIX_TRAITS}OpenClose"
TRAIT_VOLUME = f"{PREFIX_TRAITS}Volume"
TRAIT_ARMDISARM = f"{PREFIX_TRAITS}ArmDisarm"
TRAIT_HUMIDITY_SETTING = f"{PREFIX_TRAITS}HumiditySetting"

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
COMMAND_OPENCLOSE = f"{PREFIX_COMMANDS}OpenClose"
COMMAND_SET_VOLUME = f"{PREFIX_COMMANDS}setVolume"
COMMAND_VOLUME_RELATIVE = f"{PREFIX_COMMANDS}volumeRelative"
COMMAND_ARMDISARM = f"{PREFIX_COMMANDS}ArmDisarm"

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
        self.stream_info = {"cameraStreamAccessUrl": f"{async_get_url(self.hass)}{url}"}


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
        )

    def sync_attributes(self):
        """Return OnOff attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return OnOff query attributes."""
        return {"on": self.state.state != STATE_OFF}

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
    commands = []

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
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

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a humidity command."""
        domain = self.state.domain
        if domain == sensor.DOMAIN:
            raise SmartHomeError(
                ERR_NOT_SUPPORTED, "Execute is not supported by sensor"
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

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        return domain == alarm_control_panel.DOMAIN

    @staticmethod
    def might_2fa(domain, features, device_class):
        """Return if the trait might ask for 2FA."""
        return True

    def sync_attributes(self):
        """Return ArmDisarm attributes for a sync request."""
        response = {}
        levels = []
        for state in self.state_to_service:
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
        if "post_pending_state" in self.state.attributes:
            armed_state = self.state.attributes["post_pending_state"]
        else:
            armed_state = self.state.state
        response = {"isArmed": armed_state in self.state_to_service}
        if response["isArmed"]:
            response.update({"currentArmLevel": armed_state})
        return response

    async def execute(self, command, data, params, challenge):
        """Execute an ArmDisarm command."""
        if params["arm"] and not params.get("cancel"):
            if self.state.state == params["armLevel"]:
                raise SmartHomeError(ERR_ALREADY_ARMED, "System is already armed")
            if self.state.attributes["code_arm_required"]:
                _verify_pin_challenge(data, self.state, challenge)
            service = self.state_to_service[params["armLevel"]]
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
        if domain != fan.DOMAIN:
            return False

        return features & fan.SUPPORT_SET_SPEED

    def sync_attributes(self):
        """Return speed point and modes attributes for a sync request."""
        modes = self.state.attributes.get(fan.ATTR_SPEED_LIST, [])
        speeds = []
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

        return {
            "availableFanSpeeds": {"speeds": speeds, "ordered": True},
            "reversible": bool(
                self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
                & fan.SUPPORT_DIRECTION
            ),
        }

    def query_attributes(self):
        """Return speed point and modes query attributes."""
        attrs = self.state.attributes
        response = {}

        speed = attrs.get(fan.ATTR_SPEED)
        if speed is not None:
            response["on"] = speed != fan.SPEED_OFF
            response["online"] = True
            response["currentFanSpeedSetting"] = speed

        return response

    async def execute(self, command, data, params, challenge):
        """Execute an SetFanSpeed command."""
        await self.hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_SET_SPEED,
            {ATTR_ENTITY_ID: self.state.entity_id, fan.ATTR_SPEED: params["fanSpeed"]},
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
        "input source": ["input source", "input", "source"],
        "sound mode": ["sound mode", "effects"],
    }

    @staticmethod
    def supported(domain, features, device_class):
        """Test if state is supported."""
        if domain != media_player.DOMAIN:
            return False

        return (
            features & media_player.SUPPORT_SELECT_SOURCE
            or features & media_player.SUPPORT_SELECT_SOUND_MODE
        )

    def sync_attributes(self):
        """Return mode attributes for a sync request."""

        def _generate(name, settings):
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
                                "setting_synonym": self.SYNONYMS.get(
                                    setting, [setting]
                                ),
                                "lang": "en",
                            }
                        ],
                    }
                )
            return mode

        attrs = self.state.attributes
        modes = []
        if media_player.ATTR_INPUT_SOURCE_LIST in attrs:
            modes.append(
                _generate("input source", attrs[media_player.ATTR_INPUT_SOURCE_LIST])
            )

        if media_player.ATTR_SOUND_MODE_LIST in attrs:
            modes.append(
                _generate("sound mode", attrs[media_player.ATTR_SOUND_MODE_LIST])
            )

        payload = {"availableModes": modes}

        return payload

    def query_attributes(self):
        """Return current modes."""
        attrs = self.state.attributes
        response = {}
        mode_settings = {}

        if media_player.ATTR_INPUT_SOURCE_LIST in attrs:
            mode_settings["input source"] = attrs.get(media_player.ATTR_INPUT_SOURCE)

        if media_player.ATTR_SOUND_MODE_LIST in attrs:
            mode_settings["sound mode"] = attrs.get(media_player.ATTR_SOUND_MODE)

        if mode_settings:
            response["on"] = self.state.state != STATE_OFF
            response["online"] = True
            response["currentModeSettings"] = mode_settings

        return response

    async def execute(self, command, data, params, challenge):
        """Execute an SetModes command."""
        settings = params.get("updateModeSettings")
        requested_source = settings.get("input source")
        sound_mode = settings.get("sound mode")

        if requested_source:
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
