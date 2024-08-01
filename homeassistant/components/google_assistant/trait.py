"""Implement the Google Smart Home traits."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components import (
    alarm_control_panel,
    binary_sensor,
    button,
    camera,
    climate,
    cover,
    event,
    fan,
    group,
    humidifier,
    input_boolean,
    input_button,
    input_select,
    light,
    lock,
    media_player,
    scene,
    script,
    select,
    sensor,
    switch,
    vacuum,
    valve,
    water_heater,
)
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.fan import FanEntityFeature
from homeassistant.components.humidifier import HumidifierEntityFeature
from homeassistant.components.light import LightEntityFeature
from homeassistant.components.lock import STATE_JAMMED, STATE_UNLOCKING
from homeassistant.components.media_player import MediaPlayerEntityFeature, MediaType
from homeassistant.components.vacuum import VacuumEntityFeature
from homeassistant.components.valve import ValveEntityFeature
from homeassistant.components.water_heater import WaterHeaterEntityFeature
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_BATTERY_LEVEL,
    ATTR_CODE,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CAST_APP_ID_HOMEASSISTANT_MEDIA,
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
    UnitOfTemperature,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers.network import get_url
from homeassistant.util import color as color_util, dt as dt_util
from homeassistant.util.dt import utcnow
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CHALLENGE_FAILED_PIN_NEEDED,
    CHALLENGE_PIN_NEEDED,
    ERR_ALREADY_ARMED,
    ERR_ALREADY_DISARMED,
    ERR_ALREADY_STOPPED,
    ERR_CHALLENGE_NOT_SETUP,
    ERR_FUNCTION_NOT_SUPPORTED,
    ERR_NO_AVAILABLE_CHANNEL,
    ERR_NOT_SUPPORTED,
    ERR_UNSUPPORTED_INPUT,
    ERR_VALUE_OUT_OF_RANGE,
    FAN_SPEEDS,
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
TRAIT_TEMPERATURE_CONTROL = f"{PREFIX_TRAITS}TemperatureControl"
TRAIT_LOCKUNLOCK = f"{PREFIX_TRAITS}LockUnlock"
TRAIT_FANSPEED = f"{PREFIX_TRAITS}FanSpeed"
TRAIT_MODES = f"{PREFIX_TRAITS}Modes"
TRAIT_INPUTSELECTOR = f"{PREFIX_TRAITS}InputSelector"
TRAIT_OBJECTDETECTION = f"{PREFIX_TRAITS}ObjectDetection"
TRAIT_OPENCLOSE = f"{PREFIX_TRAITS}OpenClose"
TRAIT_VOLUME = f"{PREFIX_TRAITS}Volume"
TRAIT_ARMDISARM = f"{PREFIX_TRAITS}ArmDisarm"
TRAIT_HUMIDITY_SETTING = f"{PREFIX_TRAITS}HumiditySetting"
TRAIT_TRANSPORT_CONTROL = f"{PREFIX_TRAITS}TransportControl"
TRAIT_MEDIA_STATE = f"{PREFIX_TRAITS}MediaState"
TRAIT_CHANNEL = f"{PREFIX_TRAITS}Channel"
TRAIT_LOCATOR = f"{PREFIX_TRAITS}Locator"
TRAIT_ENERGYSTORAGE = f"{PREFIX_TRAITS}EnergyStorage"
TRAIT_SENSOR_STATE = f"{PREFIX_TRAITS}SensorState"

PREFIX_COMMANDS = "action.devices.commands."
COMMAND_ONOFF = f"{PREFIX_COMMANDS}OnOff"
COMMAND_GET_CAMERA_STREAM = f"{PREFIX_COMMANDS}GetCameraStream"
COMMAND_DOCK = f"{PREFIX_COMMANDS}Dock"
COMMAND_STARTSTOP = f"{PREFIX_COMMANDS}StartStop"
COMMAND_PAUSEUNPAUSE = f"{PREFIX_COMMANDS}PauseUnpause"
COMMAND_BRIGHTNESS_ABSOLUTE = f"{PREFIX_COMMANDS}BrightnessAbsolute"
COMMAND_COLOR_ABSOLUTE = f"{PREFIX_COMMANDS}ColorAbsolute"
COMMAND_ACTIVATE_SCENE = f"{PREFIX_COMMANDS}ActivateScene"
COMMAND_SET_TEMPERATURE = f"{PREFIX_COMMANDS}SetTemperature"
COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT = (
    f"{PREFIX_COMMANDS}ThermostatTemperatureSetpoint"
)
COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE = (
    f"{PREFIX_COMMANDS}ThermostatTemperatureSetRange"
)
COMMAND_THERMOSTAT_SET_MODE = f"{PREFIX_COMMANDS}ThermostatSetMode"
COMMAND_LOCKUNLOCK = f"{PREFIX_COMMANDS}LockUnlock"
COMMAND_FANSPEED = f"{PREFIX_COMMANDS}SetFanSpeed"
COMMAND_FANSPEEDRELATIVE = f"{PREFIX_COMMANDS}SetFanSpeedRelative"
COMMAND_MODES = f"{PREFIX_COMMANDS}SetModes"
COMMAND_INPUT = f"{PREFIX_COMMANDS}SetInput"
COMMAND_NEXT_INPUT = f"{PREFIX_COMMANDS}NextInput"
COMMAND_PREVIOUS_INPUT = f"{PREFIX_COMMANDS}PreviousInput"
COMMAND_OPENCLOSE = f"{PREFIX_COMMANDS}OpenClose"
COMMAND_OPENCLOSE_RELATIVE = f"{PREFIX_COMMANDS}OpenCloseRelative"
COMMAND_SET_VOLUME = f"{PREFIX_COMMANDS}setVolume"
COMMAND_VOLUME_RELATIVE = f"{PREFIX_COMMANDS}volumeRelative"
COMMAND_MUTE = f"{PREFIX_COMMANDS}mute"
COMMAND_ARMDISARM = f"{PREFIX_COMMANDS}ArmDisarm"
COMMAND_MEDIA_NEXT = f"{PREFIX_COMMANDS}mediaNext"
COMMAND_MEDIA_PAUSE = f"{PREFIX_COMMANDS}mediaPause"
COMMAND_MEDIA_PREVIOUS = f"{PREFIX_COMMANDS}mediaPrevious"
COMMAND_MEDIA_RESUME = f"{PREFIX_COMMANDS}mediaResume"
COMMAND_MEDIA_SEEK_RELATIVE = f"{PREFIX_COMMANDS}mediaSeekRelative"
COMMAND_MEDIA_SEEK_TO_POSITION = f"{PREFIX_COMMANDS}mediaSeekToPosition"
COMMAND_MEDIA_SHUFFLE = f"{PREFIX_COMMANDS}mediaShuffle"
COMMAND_MEDIA_STOP = f"{PREFIX_COMMANDS}mediaStop"
COMMAND_REVERSE = f"{PREFIX_COMMANDS}Reverse"
COMMAND_SET_HUMIDITY = f"{PREFIX_COMMANDS}SetHumidity"
COMMAND_SELECT_CHANNEL = f"{PREFIX_COMMANDS}selectChannel"
COMMAND_LOCATE = f"{PREFIX_COMMANDS}Locate"
COMMAND_CHARGE = f"{PREFIX_COMMANDS}Charge"

TRAITS: list[type[_Trait]] = []

FAN_SPEED_MAX_SPEED_COUNT = 5

COVER_VALVE_STATES = {
    cover.DOMAIN: {
        "closed": cover.STATE_CLOSED,
        "closing": cover.STATE_CLOSING,
        "open": cover.STATE_OPEN,
        "opening": cover.STATE_OPENING,
    },
    valve.DOMAIN: {
        "closed": valve.STATE_CLOSED,
        "closing": valve.STATE_CLOSING,
        "open": valve.STATE_OPEN,
        "opening": valve.STATE_OPENING,
    },
}

SERVICE_STOP_COVER_VALVE = {
    cover.DOMAIN: cover.SERVICE_STOP_COVER,
    valve.DOMAIN: valve.SERVICE_STOP_VALVE,
}
SERVICE_OPEN_COVER_VALVE = {
    cover.DOMAIN: cover.SERVICE_OPEN_COVER,
    valve.DOMAIN: valve.SERVICE_OPEN_VALVE,
}
SERVICE_CLOSE_COVER_VALVE = {
    cover.DOMAIN: cover.SERVICE_CLOSE_COVER,
    valve.DOMAIN: valve.SERVICE_CLOSE_VALVE,
}
SERVICE_TOGGLE_COVER_VALVE = {
    cover.DOMAIN: cover.SERVICE_TOGGLE,
    valve.DOMAIN: valve.SERVICE_TOGGLE,
}
SERVICE_SET_POSITION_COVER_VALVE = {
    cover.DOMAIN: cover.SERVICE_SET_COVER_POSITION,
    valve.DOMAIN: valve.SERVICE_SET_VALVE_POSITION,
}

COVER_VALVE_CURRENT_POSITION = {
    cover.DOMAIN: cover.ATTR_CURRENT_POSITION,
    valve.DOMAIN: valve.ATTR_CURRENT_POSITION,
}

COVER_VALVE_POSITION = {
    cover.DOMAIN: cover.ATTR_POSITION,
    valve.DOMAIN: valve.ATTR_POSITION,
}

COVER_VALVE_SET_POSITION_FEATURE = {
    cover.DOMAIN: CoverEntityFeature.SET_POSITION,
    valve.DOMAIN: ValveEntityFeature.SET_POSITION,
}
COVER_VALVE_STOP_FEATURE = {
    cover.DOMAIN: CoverEntityFeature.STOP,
    valve.DOMAIN: ValveEntityFeature.STOP,
}

COVER_VALVE_DOMAINS = {cover.DOMAIN, valve.DOMAIN}

FRIENDLY_DOMAIN = {cover.DOMAIN: "Cover", valve.DOMAIN: "Valve"}


def register_trait[_TraitT: _Trait](trait: type[_TraitT]) -> type[_TraitT]:
    """Decorate a class to register a trait."""
    TRAITS.append(trait)
    return trait


def _google_temp_unit(units):
    """Return Google temperature unit."""
    if units == UnitOfTemperature.FAHRENHEIT:
        return "F"
    return "C"


def _next_selected(items: list[str], selected: str | None) -> str | None:
    """Return the next item in an item list starting at given value.

    If selected is missing in items, None is returned
    """
    if selected is None:
        return None
    try:
        index = items.index(selected)
    except ValueError:
        return None

    next_item = 0 if index == len(items) - 1 else index + 1
    return items[next_item]


class _Trait(ABC):
    """Represents a Trait inside Google Assistant skill."""

    name: str
    commands: list[str] = []

    @staticmethod
    def might_2fa(domain, features, device_class):
        """Return if the trait might ask for 2FA."""
        return False

    @staticmethod
    @abstractmethod
    def supported(domain, features, device_class, attributes):
        """Test if state is supported."""

    def __init__(self, hass: HomeAssistant, state, config) -> None:
        """Initialize a trait for a state."""
        self.hass = hass
        self.state = state
        self.config = config

    def sync_attributes(self):
        """Return attributes for a sync request."""
        raise NotImplementedError

    def sync_options(self) -> dict[str, Any]:
        """Add options for the sync request."""
        return {}

    def query_attributes(self):
        """Return the attributes of this trait for this entity."""
        raise NotImplementedError

    def query_notifications(self) -> dict[str, Any] | None:
        """Return notifications payload."""

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
    def supported(domain, features, device_class, attributes):
        """Test if state is supported."""
        if domain == light.DOMAIN:
            color_modes = attributes.get(light.ATTR_SUPPORTED_COLOR_MODES)
            return light.brightness_supported(color_modes)

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
                response["brightness"] = round(100 * (brightness / 255))

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a brightness command."""
        if self.state.domain == light.DOMAIN:
            await self.hass.services.async_call(
                light.DOMAIN,
                light.SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    light.ATTR_BRIGHTNESS_PCT: params["brightness"],
                },
                blocking=not self.config.should_report_state,
                context=data.context,
            )


@register_trait
class CameraStreamTrait(_Trait):
    """Trait to stream from cameras.

    https://developers.google.com/actions/smarthome/traits/camerastream
    """

    name = TRAIT_CAMERA_STREAM
    commands = [COMMAND_GET_CAMERA_STREAM]

    stream_info: dict[str, str] | None = None

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        if domain == camera.DOMAIN:
            return features & CameraEntityFeature.STREAM

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
        url = await camera.async_request_stream(self.hass, self.state.entity_id, "hls")
        self.stream_info = {
            "cameraStreamAccessUrl": f"{get_url(self.hass)}{url}",
            "cameraStreamReceiverAppId": CAST_APP_ID_HOMEASSISTANT_MEDIA,
        }


@register_trait
class ObjectDetection(_Trait):
    """Trait to object detection.

    https://developers.google.com/actions/smarthome/traits/objectdetection
    """

    name = TRAIT_OBJECTDETECTION
    commands = []

    @staticmethod
    def supported(domain, features, device_class, _) -> bool:
        """Test if state is supported."""
        return (
            domain == event.DOMAIN and device_class == event.EventDeviceClass.DOORBELL
        )

    def sync_attributes(self):
        """Return ObjectDetection attributes for a sync request."""
        return {}

    def sync_options(self) -> dict[str, Any]:
        """Add options for the sync request."""
        return {"notificationSupportedByAgent": True}

    def query_attributes(self):
        """Return ObjectDetection query attributes."""
        return {}

    def query_notifications(self) -> dict[str, Any] | None:
        """Return notifications payload."""

        if self.state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            return None

        # Only notify if last event was less then 30 seconds ago
        time_stamp: datetime = datetime.fromisoformat(self.state.state)
        if (utcnow() - time_stamp) > timedelta(seconds=30):
            return None

        # A doorbell event is treated as an object detection of 1 unclassified object.
        # The implementation follows the pattern from the Smart Home Doorbell Guide:
        # https://developers.home.google.com/cloud-to-cloud/guides/doorbell
        # The detectionTimestamp is the time in ms from January 1, 1970, 00:00:00 (UTC)
        return {
            "ObjectDetection": {
                "objects": {
                    "unclassified": 1,
                },
                "priority": 0,
                "detectionTimestamp": int(time_stamp.timestamp() * 1000),
            },
        }

    async def execute(self, command, data, params, challenge):
        """Execute an ObjectDetection command."""


@register_trait
class OnOffTrait(_Trait):
    """Trait to offer basic on and off functionality.

    https://developers.google.com/actions/smarthome/traits/onoff
    """

    name = TRAIT_ONOFF
    commands = [COMMAND_ONOFF]

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        if domain == water_heater.DOMAIN and features & WaterHeaterEntityFeature.ON_OFF:
            return True

        if domain == climate.DOMAIN and features & (
            ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        ):
            return True

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
        if self.state.attributes.get(ATTR_ASSUMED_STATE, False):
            return {"commandOnlyOnOff": True}
        return {}

    def query_attributes(self):
        """Return OnOff query attributes."""
        return {"on": self.state.state not in (STATE_OFF, STATE_UNKNOWN)}

    async def execute(self, command, data, params, challenge):
        """Execute an OnOff command."""
        if (domain := self.state.domain) == group.DOMAIN:
            service_domain = HOMEASSISTANT_DOMAIN
            service = SERVICE_TURN_ON if params["on"] else SERVICE_TURN_OFF

        else:
            service_domain = domain
            service = SERVICE_TURN_ON if params["on"] else SERVICE_TURN_OFF

        await self.hass.services.async_call(
            service_domain,
            service,
            {ATTR_ENTITY_ID: self.state.entity_id},
            blocking=not self.config.should_report_state,
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
    def supported(domain, features, device_class, attributes):
        """Test if state is supported."""
        if domain != light.DOMAIN:
            return False

        color_modes = attributes.get(light.ATTR_SUPPORTED_COLOR_MODES)
        return light.color_temp_supported(color_modes) or light.color_supported(
            color_modes
        )

    def sync_attributes(self):
        """Return color temperature attributes for a sync request."""
        attrs = self.state.attributes
        color_modes = attrs.get(light.ATTR_SUPPORTED_COLOR_MODES)
        response = {}

        if light.color_supported(color_modes):
            response["colorModel"] = "hsv"

        if light.color_temp_supported(color_modes):
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
        color_mode = self.state.attributes.get(light.ATTR_COLOR_MODE)

        color = {}

        if light.color_supported([color_mode]):
            color_hs = self.state.attributes.get(light.ATTR_HS_COLOR)
            brightness = self.state.attributes.get(light.ATTR_BRIGHTNESS, 1)
            if color_hs is not None:
                color["spectrumHsv"] = {
                    "hue": color_hs[0],
                    "saturation": color_hs[1] / 100,
                    "value": brightness / 255,
                }

        if light.color_temp_supported([color_mode]):
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
                blocking=not self.config.should_report_state,
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
                blocking=not self.config.should_report_state,
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
                blocking=not self.config.should_report_state,
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
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        return domain in (
            button.DOMAIN,
            input_button.DOMAIN,
            scene.DOMAIN,
            script.DOMAIN,
        )

    def sync_attributes(self):
        """Return scene attributes for a sync request."""
        # None of the supported domains can support sceneReversible
        return {}

    def query_attributes(self):
        """Return scene query attributes."""
        return {}

    async def execute(self, command, data, params, challenge):
        """Execute a scene command."""
        service = SERVICE_TURN_ON
        if self.state.domain == button.DOMAIN:
            service = button.SERVICE_PRESS
        elif self.state.domain == input_button.DOMAIN:
            service = input_button.SERVICE_PRESS

        # Don't block for scripts or buttons, as they can be slow.
        await self.hass.services.async_call(
            self.state.domain,
            service,
            {ATTR_ENTITY_ID: self.state.entity_id},
            blocking=(not self.config.should_report_state)
            and self.state.domain
            not in (button.DOMAIN, input_button.DOMAIN, script.DOMAIN),
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
    def supported(domain, features, device_class, _):
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
            blocking=not self.config.should_report_state,
            context=data.context,
        )


@register_trait
class LocatorTrait(_Trait):
    """Trait to offer locate functionality.

    https://developers.google.com/actions/smarthome/traits/locator
    """

    name = TRAIT_LOCATOR
    commands = [COMMAND_LOCATE]

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        return domain == vacuum.DOMAIN and features & VacuumEntityFeature.LOCATE

    def sync_attributes(self):
        """Return locator attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return locator query attributes."""
        return {}

    async def execute(self, command, data, params, challenge):
        """Execute a locate command."""
        if params.get("silence", False):
            raise SmartHomeError(
                ERR_FUNCTION_NOT_SUPPORTED,
                "Silencing a Locate request is not yet supported",
            )

        await self.hass.services.async_call(
            self.state.domain,
            vacuum.SERVICE_LOCATE,
            {ATTR_ENTITY_ID: self.state.entity_id},
            blocking=not self.config.should_report_state,
            context=data.context,
        )


@register_trait
class EnergyStorageTrait(_Trait):
    """Trait to offer EnergyStorage functionality.

    https://developers.google.com/actions/smarthome/traits/energystorage
    """

    name = TRAIT_ENERGYSTORAGE
    commands = [COMMAND_CHARGE]

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        return domain == vacuum.DOMAIN and features & VacuumEntityFeature.BATTERY

    def sync_attributes(self):
        """Return EnergyStorage attributes for a sync request."""
        return {
            "isRechargeable": True,
            "queryOnlyEnergyStorage": True,
        }

    def query_attributes(self):
        """Return EnergyStorage query attributes."""
        battery_level = self.state.attributes.get(ATTR_BATTERY_LEVEL)
        if battery_level is None:
            return {}
        if battery_level == 100:
            descriptive_capacity_remaining = "FULL"
        elif 75 <= battery_level < 100:
            descriptive_capacity_remaining = "HIGH"
        elif 50 <= battery_level < 75:
            descriptive_capacity_remaining = "MEDIUM"
        elif 25 <= battery_level < 50:
            descriptive_capacity_remaining = "LOW"
        elif 0 <= battery_level < 25:
            descriptive_capacity_remaining = "CRITICALLY_LOW"
        return {
            "descriptiveCapacityRemaining": descriptive_capacity_remaining,
            "capacityRemaining": [{"rawValue": battery_level, "unit": "PERCENTAGE"}],
            "capacityUntilFull": [
                {"rawValue": 100 - battery_level, "unit": "PERCENTAGE"}
            ],
            "isCharging": self.state.state == vacuum.STATE_DOCKED,
            "isPluggedIn": self.state.state == vacuum.STATE_DOCKED,
        }

    async def execute(self, command, data, params, challenge):
        """Execute a dock command."""
        raise SmartHomeError(
            ERR_FUNCTION_NOT_SUPPORTED,
            "Controlling charging of a vacuum is not yet supported",
        )


@register_trait
class StartStopTrait(_Trait):
    """Trait to offer StartStop functionality.

    https://developers.google.com/actions/smarthome/traits/startstop
    """

    name = TRAIT_STARTSTOP
    commands = [COMMAND_STARTSTOP, COMMAND_PAUSEUNPAUSE]

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        if domain == vacuum.DOMAIN:
            return True

        if (
            domain in COVER_VALVE_DOMAINS
            and features & COVER_VALVE_STOP_FEATURE[domain]
        ):
            return True

        return False

    def sync_attributes(self):
        """Return StartStop attributes for a sync request."""
        domain = self.state.domain
        if domain == vacuum.DOMAIN:
            return {
                "pausable": self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
                & VacuumEntityFeature.PAUSE
                != 0
            }
        if domain in COVER_VALVE_DOMAINS:
            return {}

    def query_attributes(self):
        """Return StartStop query attributes."""
        domain = self.state.domain
        state = self.state.state

        if domain == vacuum.DOMAIN:
            return {
                "isRunning": state == vacuum.STATE_CLEANING,
                "isPaused": state == vacuum.STATE_PAUSED,
            }

        if domain in COVER_VALVE_DOMAINS:
            return {
                "isRunning": state
                in (
                    COVER_VALVE_STATES[domain]["closing"],
                    COVER_VALVE_STATES[domain]["opening"],
                )
            }

    async def execute(self, command, data, params, challenge):
        """Execute a StartStop command."""
        domain = self.state.domain
        if domain == vacuum.DOMAIN:
            return await self._execute_vacuum(command, data, params, challenge)
        if domain in COVER_VALVE_DOMAINS:
            return await self._execute_cover_or_valve(command, data, params, challenge)

    async def _execute_vacuum(self, command, data, params, challenge):
        """Execute a StartStop command."""
        if command == COMMAND_STARTSTOP:
            if params["start"]:
                await self.hass.services.async_call(
                    self.state.domain,
                    vacuum.SERVICE_START,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=not self.config.should_report_state,
                    context=data.context,
                )
            else:
                await self.hass.services.async_call(
                    self.state.domain,
                    vacuum.SERVICE_STOP,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=not self.config.should_report_state,
                    context=data.context,
                )
        elif command == COMMAND_PAUSEUNPAUSE:
            if params["pause"]:
                await self.hass.services.async_call(
                    self.state.domain,
                    vacuum.SERVICE_PAUSE,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=not self.config.should_report_state,
                    context=data.context,
                )
            else:
                await self.hass.services.async_call(
                    self.state.domain,
                    vacuum.SERVICE_START,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=not self.config.should_report_state,
                    context=data.context,
                )

    async def _execute_cover_or_valve(self, command, data, params, challenge):
        """Execute a StartStop command."""
        domain = self.state.domain
        if command == COMMAND_STARTSTOP:
            if params["start"] is False:
                if self.state.state in (
                    COVER_VALVE_STATES[domain]["closing"],
                    COVER_VALVE_STATES[domain]["opening"],
                ) or self.state.attributes.get(ATTR_ASSUMED_STATE):
                    await self.hass.services.async_call(
                        domain,
                        SERVICE_STOP_COVER_VALVE[domain],
                        {ATTR_ENTITY_ID: self.state.entity_id},
                        blocking=not self.config.should_report_state,
                        context=data.context,
                    )
                else:
                    raise SmartHomeError(
                        ERR_ALREADY_STOPPED,
                        f"{FRIENDLY_DOMAIN[domain]} is already stopped",
                    )
            else:
                await self.hass.services.async_call(
                    domain,
                    SERVICE_TOGGLE_COVER_VALVE[domain],
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=not self.config.should_report_state,
                    context=data.context,
                )
        else:
            raise SmartHomeError(
                ERR_NOT_SUPPORTED, f"Command {command} is not supported"
            )


@register_trait
class TemperatureControlTrait(_Trait):
    """Trait for devices (other than thermostats) that support controlling temperature.

    Control the target temperature of water heaters.
    Offers a workaround for Temperature sensors by setting queryOnlyTemperatureControl
    in the response.

    https://developers.google.com/assistant/smarthome/traits/temperaturecontrol
    """

    name = TRAIT_TEMPERATURE_CONTROL

    commands = [
        COMMAND_SET_TEMPERATURE,
    ]

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        return (
            domain == water_heater.DOMAIN
            and features & WaterHeaterEntityFeature.TARGET_TEMPERATURE
        ) or (
            domain == sensor.DOMAIN
            and device_class == sensor.SensorDeviceClass.TEMPERATURE
        )

    def sync_attributes(self):
        """Return temperature attributes for a sync request."""
        response = {}
        domain = self.state.domain
        attrs = self.state.attributes
        unit = self.hass.config.units.temperature_unit
        response["temperatureUnitForUX"] = _google_temp_unit(unit)

        if domain == water_heater.DOMAIN:
            min_temp = round(
                TemperatureConverter.convert(
                    float(attrs[water_heater.ATTR_MIN_TEMP]),
                    unit,
                    UnitOfTemperature.CELSIUS,
                )
            )
            max_temp = round(
                TemperatureConverter.convert(
                    float(attrs[water_heater.ATTR_MAX_TEMP]),
                    unit,
                    UnitOfTemperature.CELSIUS,
                )
            )
            response["temperatureRange"] = {
                "minThresholdCelsius": min_temp,
                "maxThresholdCelsius": max_temp,
            }
        else:
            response["queryOnlyTemperatureControl"] = True
            response["temperatureRange"] = {
                "minThresholdCelsius": -100,
                "maxThresholdCelsius": 100,
            }

        return response

    def query_attributes(self):
        """Return temperature states."""
        response = {}
        domain = self.state.domain
        unit = self.hass.config.units.temperature_unit
        if domain == water_heater.DOMAIN:
            target_temp = self.state.attributes[water_heater.ATTR_TEMPERATURE]
            current_temp = self.state.attributes[water_heater.ATTR_CURRENT_TEMPERATURE]
            if target_temp not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                response["temperatureSetpointCelsius"] = round(
                    TemperatureConverter.convert(
                        float(target_temp),
                        unit,
                        UnitOfTemperature.CELSIUS,
                    ),
                    1,
                )
            if current_temp is not None:
                response["temperatureAmbientCelsius"] = round(
                    TemperatureConverter.convert(
                        float(current_temp),
                        unit,
                        UnitOfTemperature.CELSIUS,
                    ),
                    1,
                )
            return response

        # domain == sensor.DOMAIN
        current_temp = self.state.state
        if current_temp not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            temp = round(
                TemperatureConverter.convert(
                    float(current_temp), unit, UnitOfTemperature.CELSIUS
                ),
                1,
            )
            response["temperatureSetpointCelsius"] = temp
            response["temperatureAmbientCelsius"] = temp

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a temperature point or mode command."""
        # All sent in temperatures are always in Celsius
        domain = self.state.domain
        unit = self.hass.config.units.temperature_unit

        if domain == water_heater.DOMAIN and command == COMMAND_SET_TEMPERATURE:
            min_temp = self.state.attributes[water_heater.ATTR_MIN_TEMP]
            max_temp = self.state.attributes[water_heater.ATTR_MAX_TEMP]
            temp = TemperatureConverter.convert(
                params["temperature"], UnitOfTemperature.CELSIUS, unit
            )
            if unit == UnitOfTemperature.FAHRENHEIT:
                temp = round(temp)
            if temp < min_temp or temp > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    f"Temperature should be between {min_temp} and {max_temp}",
                )

            await self.hass.services.async_call(
                water_heater.DOMAIN,
                water_heater.SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: self.state.entity_id, ATTR_TEMPERATURE: temp},
                blocking=not self.config.should_report_state,
                context=data.context,
            )
            return

        raise SmartHomeError(ERR_NOT_SUPPORTED, f"Execute is not supported by {domain}")


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
        climate.HVACMode.HEAT: "heat",
        climate.HVACMode.COOL: "cool",
        climate.HVACMode.OFF: "off",
        climate.HVACMode.AUTO: "auto",
        climate.HVACMode.HEAT_COOL: "heatcool",
        climate.HVACMode.FAN_ONLY: "fan-only",
        climate.HVACMode.DRY: "dry",
    }
    google_to_hvac = {value: key for key, value in hvac_to_google.items()}

    preset_to_google = {climate.PRESET_ECO: "eco"}
    google_to_preset = {value: key for key, value in preset_to_google.items()}

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        return domain == climate.DOMAIN

    @property
    def climate_google_modes(self):
        """Return supported Google modes."""
        modes = []
        attrs = self.state.attributes

        for mode in attrs.get(climate.ATTR_HVAC_MODES) or []:
            google_mode = self.hvac_to_google.get(mode)
            if google_mode and google_mode not in modes:
                modes.append(google_mode)

        for preset in attrs.get(climate.ATTR_PRESET_MODES) or []:
            google_mode = self.preset_to_google.get(preset)
            if google_mode and google_mode not in modes:
                modes.append(google_mode)

        return modes

    def sync_attributes(self):
        """Return temperature point and modes attributes for a sync request."""
        response = {}
        attrs = self.state.attributes
        unit = self.hass.config.units.temperature_unit
        response["thermostatTemperatureUnit"] = _google_temp_unit(unit)

        min_temp = round(
            TemperatureConverter.convert(
                float(attrs[climate.ATTR_MIN_TEMP]),
                unit,
                UnitOfTemperature.CELSIUS,
            )
        )
        max_temp = round(
            TemperatureConverter.convert(
                float(attrs[climate.ATTR_MAX_TEMP]),
                unit,
                UnitOfTemperature.CELSIUS,
            )
        )
        response["thermostatTemperatureRange"] = {
            "minThresholdCelsius": min_temp,
            "maxThresholdCelsius": max_temp,
        }

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
        response["availableThermostatModes"] = modes

        return response

    def query_attributes(self):
        """Return temperature point and modes query attributes."""
        response = {}
        attrs = self.state.attributes
        unit = self.hass.config.units.temperature_unit

        operation = self.state.state
        preset = attrs.get(climate.ATTR_PRESET_MODE)
        supported = attrs.get(ATTR_SUPPORTED_FEATURES, 0)

        if preset in self.preset_to_google:
            response["thermostatMode"] = self.preset_to_google[preset]
        else:
            response["thermostatMode"] = self.hvac_to_google.get(operation, "none")

        current_temp = attrs.get(climate.ATTR_CURRENT_TEMPERATURE)
        if current_temp is not None:
            response["thermostatTemperatureAmbient"] = round(
                TemperatureConverter.convert(
                    current_temp, unit, UnitOfTemperature.CELSIUS
                ),
                1,
            )

        current_humidity = attrs.get(climate.ATTR_CURRENT_HUMIDITY)
        if current_humidity is not None:
            response["thermostatHumidityAmbient"] = current_humidity

        if operation in (climate.HVACMode.AUTO, climate.HVACMode.HEAT_COOL):
            if supported & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE:
                response["thermostatTemperatureSetpointHigh"] = round(
                    TemperatureConverter.convert(
                        attrs[climate.ATTR_TARGET_TEMP_HIGH],
                        unit,
                        UnitOfTemperature.CELSIUS,
                    ),
                    1,
                )
                response["thermostatTemperatureSetpointLow"] = round(
                    TemperatureConverter.convert(
                        attrs[climate.ATTR_TARGET_TEMP_LOW],
                        unit,
                        UnitOfTemperature.CELSIUS,
                    ),
                    1,
                )
            elif (target_temp := attrs.get(ATTR_TEMPERATURE)) is not None:
                target_temp = round(
                    TemperatureConverter.convert(
                        target_temp, unit, UnitOfTemperature.CELSIUS
                    ),
                    1,
                )
                response["thermostatTemperatureSetpointHigh"] = target_temp
                response["thermostatTemperatureSetpointLow"] = target_temp
        elif (target_temp := attrs.get(ATTR_TEMPERATURE)) is not None:
            response["thermostatTemperatureSetpoint"] = round(
                TemperatureConverter.convert(
                    target_temp, unit, UnitOfTemperature.CELSIUS
                ),
                1,
            )

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a temperature point or mode command."""
        # All sent in temperatures are always in Celsius
        unit = self.hass.config.units.temperature_unit
        min_temp = self.state.attributes[climate.ATTR_MIN_TEMP]
        max_temp = self.state.attributes[climate.ATTR_MAX_TEMP]

        if command == COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT:
            temp = TemperatureConverter.convert(
                params["thermostatTemperatureSetpoint"], UnitOfTemperature.CELSIUS, unit
            )
            if unit == UnitOfTemperature.FAHRENHEIT:
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
                blocking=not self.config.should_report_state,
                context=data.context,
            )

        elif command == COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE:
            temp_high = TemperatureConverter.convert(
                params["thermostatTemperatureSetpointHigh"],
                UnitOfTemperature.CELSIUS,
                unit,
            )
            if unit == UnitOfTemperature.FAHRENHEIT:
                temp_high = round(temp_high)

            if temp_high < min_temp or temp_high > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    (
                        "Upper bound for temperature range should be between "
                        f"{min_temp} and {max_temp}"
                    ),
                )

            temp_low = TemperatureConverter.convert(
                params["thermostatTemperatureSetpointLow"],
                UnitOfTemperature.CELSIUS,
                unit,
            )
            if unit == UnitOfTemperature.FAHRENHEIT:
                temp_low = round(temp_low)

            if temp_low < min_temp or temp_low > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    (
                        "Lower bound for temperature range should be between "
                        f"{min_temp} and {max_temp}"
                    ),
                )

            supported = self.state.attributes.get(ATTR_SUPPORTED_FEATURES)
            svc_data = {ATTR_ENTITY_ID: self.state.entity_id}

            if supported & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE:
                svc_data[climate.ATTR_TARGET_TEMP_HIGH] = temp_high
                svc_data[climate.ATTR_TARGET_TEMP_LOW] = temp_low
            else:
                svc_data[ATTR_TEMPERATURE] = (temp_high + temp_low) / 2

            await self.hass.services.async_call(
                climate.DOMAIN,
                climate.SERVICE_SET_TEMPERATURE,
                svc_data,
                blocking=not self.config.should_report_state,
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
                    blocking=not self.config.should_report_state,
                    context=data.context,
                )
                return

            if target_mode == "off":
                await self.hass.services.async_call(
                    climate.DOMAIN,
                    SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=not self.config.should_report_state,
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
                    blocking=not self.config.should_report_state,
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
                blocking=not self.config.should_report_state,
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
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        if domain == humidifier.DOMAIN:
            return True

        return (
            domain == sensor.DOMAIN
            and device_class == sensor.SensorDeviceClass.HUMIDITY
        )

    def sync_attributes(self):
        """Return humidity attributes for a sync request."""
        response = {}
        attrs = self.state.attributes
        domain = self.state.domain

        if domain == sensor.DOMAIN:
            device_class = attrs.get(ATTR_DEVICE_CLASS)
            if device_class == sensor.SensorDeviceClass.HUMIDITY:
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
            if device_class == sensor.SensorDeviceClass.HUMIDITY:
                current_humidity = self.state.state
                if current_humidity not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    response["humidityAmbientPercent"] = round(float(current_humidity))

        elif domain == humidifier.DOMAIN:
            target_humidity: int | None = attrs.get(humidifier.ATTR_HUMIDITY)
            if target_humidity is not None:
                response["humiditySetpointPercent"] = target_humidity
            current_humidity: int | None = attrs.get(humidifier.ATTR_CURRENT_HUMIDITY)
            if current_humidity is not None:
                response["humidityAmbientPercent"] = current_humidity

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a humidity command."""
        if self.state.domain == sensor.DOMAIN:
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
                blocking=not self.config.should_report_state,
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
    def supported(domain, features, device_class, _):
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
        if self.state.state == STATE_JAMMED:
            return {"isJammed": True}

        # If its unlocking its not yet unlocked so we consider is locked
        return {"isLocked": self.state.state in (STATE_UNLOCKING, STATE_LOCKED)}

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
            blocking=not self.config.should_report_state,
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
        STATE_ALARM_ARMED_NIGHT: SERVICE_ALARM_ARM_NIGHT,
        STATE_ALARM_ARMED_AWAY: SERVICE_ALARM_ARM_AWAY,
        STATE_ALARM_ARMED_CUSTOM_BYPASS: SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        STATE_ALARM_TRIGGERED: SERVICE_ALARM_TRIGGER,
    }

    state_to_support = {
        STATE_ALARM_ARMED_HOME: AlarmControlPanelEntityFeature.ARM_HOME,
        STATE_ALARM_ARMED_NIGHT: AlarmControlPanelEntityFeature.ARM_NIGHT,
        STATE_ALARM_ARMED_AWAY: AlarmControlPanelEntityFeature.ARM_AWAY,
        STATE_ALARM_ARMED_CUSTOM_BYPASS: AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
        STATE_ALARM_TRIGGERED: AlarmControlPanelEntityFeature.TRIGGER,
    }
    """The list of states to support in increasing security state."""

    @staticmethod
    def supported(domain, features, device_class, _):
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

    def _default_arm_state(self):
        states = self._supported_states()

        if STATE_ALARM_TRIGGERED in states:
            states.remove(STATE_ALARM_TRIGGERED)

        if not states:
            raise SmartHomeError(ERR_NOT_SUPPORTED, "ArmLevel missing")

        return states[0]

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

        response["availableArmLevels"] = {"levels": levels, "ordered": True}
        return response

    def query_attributes(self):
        """Return ArmDisarm query attributes."""
        armed_state = self.state.attributes.get("next_state", self.state.state)

        if armed_state in self.state_to_service:
            return {"isArmed": True, "currentArmLevel": armed_state}
        return {
            "isArmed": False,
            "currentArmLevel": self._default_arm_state(),
        }

    async def execute(self, command, data, params, challenge):
        """Execute an ArmDisarm command."""
        if params["arm"] and not params.get("cancel"):
            # If no arm level given, we we arm the first supported
            # level in state_to_support.
            if not (arm_level := params.get("armLevel")):
                arm_level = self._default_arm_state()

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
            blocking=not self.config.should_report_state,
            context=data.context,
        )


def _get_fan_speed(speed_name: str) -> dict[str, Any]:
    """Return a fan speed synonyms for a speed name."""
    speed_synonyms = FAN_SPEEDS.get(speed_name, [f"{speed_name}"])
    return {
        "speed_name": speed_name,
        "speed_values": [
            {
                "speed_synonym": speed_synonyms,
                "lang": "en",
            }
        ],
    }


@register_trait
class FanSpeedTrait(_Trait):
    """Trait to control speed of Fan.

    https://developers.google.com/actions/smarthome/traits/fanspeed
    """

    name = TRAIT_FANSPEED
    commands = [COMMAND_FANSPEED, COMMAND_REVERSE]

    def __init__(self, hass, state, config):
        """Initialize a trait for a state."""
        super().__init__(hass, state, config)
        if state.domain == fan.DOMAIN:
            speed_count = min(
                FAN_SPEED_MAX_SPEED_COUNT,
                round(
                    100 / (self.state.attributes.get(fan.ATTR_PERCENTAGE_STEP) or 1.0)
                ),
            )
            self._ordered_speed = [
                f"{speed}/{speed_count}" for speed in range(1, speed_count + 1)
            ]

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        if domain == fan.DOMAIN:
            return features & FanEntityFeature.SET_SPEED
        if domain == climate.DOMAIN:
            return features & ClimateEntityFeature.FAN_MODE
        return False

    def sync_attributes(self):
        """Return speed point and modes attributes for a sync request."""
        domain = self.state.domain
        speeds = []
        result = {}

        if domain == fan.DOMAIN:
            reversible = bool(
                self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
                & FanEntityFeature.DIRECTION
            )

            result.update(
                {
                    "reversible": reversible,
                    "supportsFanSpeedPercent": True,
                }
            )

            if self._ordered_speed:
                result.update(
                    {
                        "availableFanSpeeds": {
                            "speeds": [
                                _get_fan_speed(speed) for speed in self._ordered_speed
                            ],
                            "ordered": True,
                        },
                    }
                )

        elif domain == climate.DOMAIN:
            modes = self.state.attributes.get(climate.ATTR_FAN_MODES) or []
            for mode in modes:
                speed = {
                    "speed_name": mode,
                    "speed_values": [{"speed_synonym": [mode], "lang": "en"}],
                }
                speeds.append(speed)

            result.update(
                {
                    "reversible": False,
                    "availableFanSpeeds": {"speeds": speeds, "ordered": True},
                }
            )

        return result

    def query_attributes(self):
        """Return speed point and modes query attributes."""

        attrs = self.state.attributes
        domain = self.state.domain
        response = {}
        if domain == climate.DOMAIN:
            speed = attrs.get(climate.ATTR_FAN_MODE) or "off"
            response["currentFanSpeedSetting"] = speed

        if domain == fan.DOMAIN:
            percent = attrs.get(fan.ATTR_PERCENTAGE) or 0
            response["currentFanSpeedPercent"] = percent
            response["currentFanSpeedSetting"] = percentage_to_ordered_list_item(
                self._ordered_speed, percent
            )

        return response

    async def execute_fanspeed(self, data, params):
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
                blocking=not self.config.should_report_state,
                context=data.context,
            )

        if domain == fan.DOMAIN:
            if fan_speed := params.get("fanSpeed"):
                fan_speed_percent = ordered_list_item_to_percentage(
                    self._ordered_speed, fan_speed
                )
            else:
                fan_speed_percent = params.get("fanSpeedPercent")

            await self.hass.services.async_call(
                fan.DOMAIN,
                fan.SERVICE_SET_PERCENTAGE,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    fan.ATTR_PERCENTAGE: fan_speed_percent,
                },
                blocking=not self.config.should_report_state,
                context=data.context,
            )

    async def execute_reverse(self, data, params):
        """Execute a Reverse command."""
        if self.state.domain == fan.DOMAIN:
            if self.state.attributes.get(fan.ATTR_DIRECTION) == fan.DIRECTION_FORWARD:
                direction = fan.DIRECTION_REVERSE
            else:
                direction = fan.DIRECTION_FORWARD

            await self.hass.services.async_call(
                fan.DOMAIN,
                fan.SERVICE_SET_DIRECTION,
                {ATTR_ENTITY_ID: self.state.entity_id, fan.ATTR_DIRECTION: direction},
                blocking=not self.config.should_report_state,
                context=data.context,
            )

    async def execute(self, command, data, params, challenge):
        """Execute a smart home command."""
        if command == COMMAND_FANSPEED:
            await self.execute_fanspeed(data, params)
        elif command == COMMAND_REVERSE:
            await self.execute_reverse(data, params)


@register_trait
class ModesTrait(_Trait):
    """Trait to set modes.

    https://developers.google.com/actions/smarthome/traits/modes
    """

    name = TRAIT_MODES
    commands = [COMMAND_MODES]

    SYNONYMS = {
        "preset mode": ["preset mode", "mode", "preset"],
        "sound mode": ["sound mode", "effects"],
        "option": ["option", "setting", "mode", "value"],
    }

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        if domain == fan.DOMAIN and features & FanEntityFeature.PRESET_MODE:
            return True

        if domain == input_select.DOMAIN:
            return True

        if domain == select.DOMAIN:
            return True

        if domain == humidifier.DOMAIN and features & HumidifierEntityFeature.MODES:
            return True

        if domain == light.DOMAIN and features & LightEntityFeature.EFFECT:
            return True

        if (
            domain == water_heater.DOMAIN
            and features & WaterHeaterEntityFeature.OPERATION_MODE
        ):
            return True

        if domain != media_player.DOMAIN:
            return False

        return features & MediaPlayerEntityFeature.SELECT_SOUND_MODE

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
            (fan.DOMAIN, fan.ATTR_PRESET_MODES, "preset mode"),
            (media_player.DOMAIN, media_player.ATTR_SOUND_MODE_LIST, "sound mode"),
            (input_select.DOMAIN, input_select.ATTR_OPTIONS, "option"),
            (select.DOMAIN, select.ATTR_OPTIONS, "option"),
            (humidifier.DOMAIN, humidifier.ATTR_AVAILABLE_MODES, "mode"),
            (light.DOMAIN, light.ATTR_EFFECT_LIST, "effect"),
            (water_heater.DOMAIN, water_heater.ATTR_OPERATION_LIST, "operation mode"),
        ):
            if self.state.domain != domain:
                continue

            if (items := self.state.attributes.get(attr)) is not None:
                modes.append(self._generate(name, items))

            # Shortcut since all domains are currently unique
            break

        return {"availableModes": modes}

    def query_attributes(self):
        """Return current modes."""
        attrs = self.state.attributes
        response = {}
        mode_settings = {}

        if self.state.domain == fan.DOMAIN:
            if fan.ATTR_PRESET_MODES in attrs:
                mode_settings["preset mode"] = attrs.get(fan.ATTR_PRESET_MODE)
        elif self.state.domain == media_player.DOMAIN:
            if media_player.ATTR_SOUND_MODE_LIST in attrs:
                mode_settings["sound mode"] = attrs.get(media_player.ATTR_SOUND_MODE)
        elif self.state.domain in (input_select.DOMAIN, select.DOMAIN):
            mode_settings["option"] = self.state.state
        elif self.state.domain == humidifier.DOMAIN:
            if ATTR_MODE in attrs:
                mode_settings["mode"] = attrs.get(ATTR_MODE)
        elif self.state.domain == water_heater.DOMAIN:
            if water_heater.ATTR_OPERATION_MODE in attrs:
                mode_settings["operation mode"] = attrs.get(
                    water_heater.ATTR_OPERATION_MODE
                )
        elif self.state.domain == light.DOMAIN and (
            effect := attrs.get(light.ATTR_EFFECT)
        ):
            mode_settings["effect"] = effect

        if mode_settings:
            response["on"] = self.state.state not in (STATE_OFF, STATE_UNKNOWN)
            response["currentModeSettings"] = mode_settings

        return response

    async def execute(self, command, data, params, challenge):
        """Execute a SetModes command."""
        settings = params.get("updateModeSettings")

        if self.state.domain == fan.DOMAIN:
            preset_mode = settings["preset mode"]
            await self.hass.services.async_call(
                fan.DOMAIN,
                fan.SERVICE_SET_PRESET_MODE,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    fan.ATTR_PRESET_MODE: preset_mode,
                },
                blocking=not self.config.should_report_state,
                context=data.context,
            )
            return

        if self.state.domain == input_select.DOMAIN:
            option = settings["option"]
            await self.hass.services.async_call(
                input_select.DOMAIN,
                input_select.SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    input_select.ATTR_OPTION: option,
                },
                blocking=not self.config.should_report_state,
                context=data.context,
            )
            return

        if self.state.domain == select.DOMAIN:
            option = settings["option"]
            await self.hass.services.async_call(
                select.DOMAIN,
                select.SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    select.ATTR_OPTION: option,
                },
                blocking=not self.config.should_report_state,
                context=data.context,
            )
            return

        if self.state.domain == humidifier.DOMAIN:
            requested_mode = settings["mode"]
            await self.hass.services.async_call(
                humidifier.DOMAIN,
                humidifier.SERVICE_SET_MODE,
                {
                    ATTR_MODE: requested_mode,
                    ATTR_ENTITY_ID: self.state.entity_id,
                },
                blocking=not self.config.should_report_state,
                context=data.context,
            )
            return

        if self.state.domain == water_heater.DOMAIN:
            requested_mode = settings["operation mode"]
            await self.hass.services.async_call(
                water_heater.DOMAIN,
                water_heater.SERVICE_SET_OPERATION_MODE,
                {
                    water_heater.ATTR_OPERATION_MODE: requested_mode,
                    ATTR_ENTITY_ID: self.state.entity_id,
                },
                blocking=not self.config.should_report_state,
                context=data.context,
            )
            return

        if self.state.domain == light.DOMAIN:
            requested_effect = settings["effect"]
            await self.hass.services.async_call(
                light.DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    light.ATTR_EFFECT: requested_effect,
                },
                blocking=not self.config.should_report_state,
                context=data.context,
            )
            return

        if self.state.domain == media_player.DOMAIN and (
            sound_mode := settings.get("sound mode")
        ):
            await self.hass.services.async_call(
                media_player.DOMAIN,
                media_player.SERVICE_SELECT_SOUND_MODE,
                {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    media_player.ATTR_SOUND_MODE: sound_mode,
                },
                blocking=not self.config.should_report_state,
                context=data.context,
            )

        _LOGGER.info(
            "Received an Options command for unrecognised domain %s",
            self.state.domain,
        )
        return


@register_trait
class InputSelectorTrait(_Trait):
    """Trait to set modes.

    https://developers.google.com/assistant/smarthome/traits/inputselector
    """

    name = TRAIT_INPUTSELECTOR
    commands = [COMMAND_INPUT, COMMAND_NEXT_INPUT, COMMAND_PREVIOUS_INPUT]

    SYNONYMS: dict[str, list[str]] = {}

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        if domain == media_player.DOMAIN and (
            features & MediaPlayerEntityFeature.SELECT_SOURCE
        ):
            return True

        return False

    def sync_attributes(self):
        """Return mode attributes for a sync request."""
        attrs = self.state.attributes
        sourcelist: list[str] = attrs.get(media_player.ATTR_INPUT_SOURCE_LIST) or []
        inputs = [
            {"key": source, "names": [{"name_synonym": [source], "lang": "en"}]}
            for source in sourcelist
        ]

        return {"availableInputs": inputs, "orderedInputs": True}

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
            blocking=not self.config.should_report_state,
            context=data.context,
        )


@register_trait
class OpenCloseTrait(_Trait):
    """Trait to open and close a cover.

    https://developers.google.com/actions/smarthome/traits/openclose
    """

    # Cover device classes that require 2FA
    COVER_2FA = (
        cover.CoverDeviceClass.DOOR,
        cover.CoverDeviceClass.GARAGE,
        cover.CoverDeviceClass.GATE,
    )

    name = TRAIT_OPENCLOSE
    commands = [COMMAND_OPENCLOSE, COMMAND_OPENCLOSE_RELATIVE]

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        if domain in COVER_VALVE_DOMAINS:
            return True

        return domain == binary_sensor.DOMAIN and device_class in (
            binary_sensor.BinarySensorDeviceClass.DOOR,
            binary_sensor.BinarySensorDeviceClass.GARAGE_DOOR,
            binary_sensor.BinarySensorDeviceClass.LOCK,
            binary_sensor.BinarySensorDeviceClass.OPENING,
            binary_sensor.BinarySensorDeviceClass.WINDOW,
        )

    @staticmethod
    def might_2fa(domain, features, device_class):
        """Return if the trait might ask for 2FA."""
        return domain == cover.DOMAIN and device_class in OpenCloseTrait.COVER_2FA

    def sync_attributes(self):
        """Return opening direction."""
        response = {}
        features = self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if self.state.domain == binary_sensor.DOMAIN:
            response["queryOnlyOpenClose"] = True
            response["discreteOnlyOpenClose"] = True
        elif (
            self.state.domain == cover.DOMAIN
            and features & CoverEntityFeature.SET_POSITION == 0
        ):
            response["discreteOnlyOpenClose"] = True

            if (
                features & CoverEntityFeature.OPEN == 0
                and features & CoverEntityFeature.CLOSE == 0
            ):
                response["queryOnlyOpenClose"] = True
        elif (
            self.state.domain == valve.DOMAIN
            and features & ValveEntityFeature.SET_POSITION == 0
        ):
            response["discreteOnlyOpenClose"] = True

            if (
                features & ValveEntityFeature.OPEN == 0
                and features & ValveEntityFeature.CLOSE == 0
            ):
                response["queryOnlyOpenClose"] = True

        if self.state.attributes.get(ATTR_ASSUMED_STATE):
            response["commandOnlyOpenClose"] = True

        return response

    def query_attributes(self):
        """Return state query attributes."""
        domain = self.state.domain
        response = {}

        # When it's an assumed state, we will return empty state
        # This shouldn't happen because we set `commandOnlyOpenClose`
        # but Google still queries. Erroring here will cause device
        # to show up offline.
        if self.state.attributes.get(ATTR_ASSUMED_STATE):
            return response

        if domain in COVER_VALVE_DOMAINS:
            if self.state.state == STATE_UNKNOWN:
                raise SmartHomeError(
                    ERR_NOT_SUPPORTED, "Querying state is not supported"
                )

            position = self.state.attributes.get(COVER_VALVE_CURRENT_POSITION[domain])

            if position is not None:
                response["openPercent"] = position
            elif self.state.state != COVER_VALVE_STATES[domain]["closed"]:
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
        features = self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if domain in COVER_VALVE_DOMAINS:
            svc_params = {ATTR_ENTITY_ID: self.state.entity_id}
            should_verify = False
            if command == COMMAND_OPENCLOSE_RELATIVE:
                position = self.state.attributes.get(
                    COVER_VALVE_CURRENT_POSITION[domain]
                )
                if position is None:
                    raise SmartHomeError(
                        ERR_NOT_SUPPORTED,
                        "Current position not know for relative command",
                    )
                position = max(0, min(100, position + params["openRelativePercent"]))
            else:
                position = params["openPercent"]

            if position == 0:
                service = SERVICE_CLOSE_COVER_VALVE[domain]
                should_verify = False
            elif position == 100:
                service = SERVICE_OPEN_COVER_VALVE[domain]
                should_verify = True
            elif features & COVER_VALVE_SET_POSITION_FEATURE[domain]:
                service = SERVICE_SET_POSITION_COVER_VALVE[domain]
                if position > 0:
                    should_verify = True
                svc_params[COVER_VALVE_POSITION[domain]] = position
            else:
                raise SmartHomeError(
                    ERR_NOT_SUPPORTED, "No support for partial open close"
                )

            if (
                should_verify
                and self.state.attributes.get(ATTR_DEVICE_CLASS)
                in OpenCloseTrait.COVER_2FA
            ):
                _verify_pin_challenge(data, self.state, challenge)

            await self.hass.services.async_call(
                domain,
                service,
                svc_params,
                blocking=not self.config.should_report_state,
                context=data.context,
            )


@register_trait
class VolumeTrait(_Trait):
    """Trait to control volume of a device.

    https://developers.google.com/actions/smarthome/traits/volume
    """

    name = TRAIT_VOLUME
    commands = [COMMAND_SET_VOLUME, COMMAND_VOLUME_RELATIVE, COMMAND_MUTE]

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if trait is supported."""
        if domain == media_player.DOMAIN:
            return features & (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )

        return False

    def sync_attributes(self):
        """Return volume attributes for a sync request."""
        features = self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        return {
            "volumeCanMuteAndUnmute": bool(
                features & MediaPlayerEntityFeature.VOLUME_MUTE
            ),
            "commandOnlyVolume": self.state.attributes.get(ATTR_ASSUMED_STATE, False),
            # Volume amounts in SET_VOLUME and VOLUME_RELATIVE are on a scale
            # from 0 to this value.
            "volumeMaxLevel": 100,
            # Default change for queries like "Hey Google, volume up".
            # 10% corresponds to the default behavior for the
            # media_player.volume{up,down} services.
            "levelStepSize": 10,
        }

    def query_attributes(self):
        """Return volume query attributes."""
        response = {}

        level = self.state.attributes.get(media_player.ATTR_MEDIA_VOLUME_LEVEL)
        if level is not None:
            # Convert 0.0-1.0 to 0-100
            response["currentVolume"] = round(level * 100)

        muted = self.state.attributes.get(media_player.ATTR_MEDIA_VOLUME_MUTED)
        if muted is not None:
            response["isMuted"] = bool(muted)

        return response

    async def _set_volume_absolute(self, data, level):
        await self.hass.services.async_call(
            media_player.DOMAIN,
            media_player.SERVICE_VOLUME_SET,
            {
                ATTR_ENTITY_ID: self.state.entity_id,
                media_player.ATTR_MEDIA_VOLUME_LEVEL: level,
            },
            blocking=not self.config.should_report_state,
            context=data.context,
        )

    async def _execute_set_volume(self, data, params):
        level = max(0, min(100, params["volumeLevel"]))

        if not (
            self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            & MediaPlayerEntityFeature.VOLUME_SET
        ):
            raise SmartHomeError(ERR_NOT_SUPPORTED, "Command not supported")

        await self._set_volume_absolute(data, level / 100)

    async def _execute_volume_relative(self, data, params):
        relative = params["relativeSteps"]
        features = self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if features & MediaPlayerEntityFeature.VOLUME_SET:
            current = self.state.attributes.get(media_player.ATTR_MEDIA_VOLUME_LEVEL)
            target = max(0.0, min(1.0, current + relative / 100))

            await self._set_volume_absolute(data, target)

        elif features & MediaPlayerEntityFeature.VOLUME_STEP:
            svc = media_player.SERVICE_VOLUME_UP
            if relative < 0:
                svc = media_player.SERVICE_VOLUME_DOWN
                relative = -relative

            for _ in range(relative):
                await self.hass.services.async_call(
                    media_player.DOMAIN,
                    svc,
                    {ATTR_ENTITY_ID: self.state.entity_id},
                    blocking=not self.config.should_report_state,
                    context=data.context,
                )
        else:
            raise SmartHomeError(ERR_NOT_SUPPORTED, "Command not supported")

    async def _execute_mute(self, data, params):
        mute = params["mute"]

        if not (
            self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            & MediaPlayerEntityFeature.VOLUME_MUTE
        ):
            raise SmartHomeError(ERR_NOT_SUPPORTED, "Command not supported")

        await self.hass.services.async_call(
            media_player.DOMAIN,
            media_player.SERVICE_VOLUME_MUTE,
            {
                ATTR_ENTITY_ID: self.state.entity_id,
                media_player.ATTR_MEDIA_VOLUME_MUTED: mute,
            },
            blocking=not self.config.should_report_state,
            context=data.context,
        )

    async def execute(self, command, data, params, challenge):
        """Execute a volume command."""
        if command == COMMAND_SET_VOLUME:
            await self._execute_set_volume(data, params)
        elif command == COMMAND_VOLUME_RELATIVE:
            await self._execute_volume_relative(data, params)
        elif command == COMMAND_MUTE:
            await self._execute_mute(data, params)
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

    if challenge.get("pin") != data.config.secure_devices_pin:
        raise ChallengeNeeded(CHALLENGE_FAILED_PIN_NEEDED)


MEDIA_COMMAND_SUPPORT_MAPPING = {
    COMMAND_MEDIA_NEXT: MediaPlayerEntityFeature.NEXT_TRACK,
    COMMAND_MEDIA_PAUSE: MediaPlayerEntityFeature.PAUSE,
    COMMAND_MEDIA_PREVIOUS: MediaPlayerEntityFeature.PREVIOUS_TRACK,
    COMMAND_MEDIA_RESUME: MediaPlayerEntityFeature.PLAY,
    COMMAND_MEDIA_SEEK_RELATIVE: MediaPlayerEntityFeature.SEEK,
    COMMAND_MEDIA_SEEK_TO_POSITION: MediaPlayerEntityFeature.SEEK,
    COMMAND_MEDIA_SHUFFLE: MediaPlayerEntityFeature.SHUFFLE_SET,
    COMMAND_MEDIA_STOP: MediaPlayerEntityFeature.STOP,
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
    def supported(domain, features, device_class, _):
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
                now = dt_util.utcnow()
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
            blocking=not self.config.should_report_state,
            context=data.context,
        )


@register_trait
class MediaStateTrait(_Trait):
    """Trait to get media playback state.

    https://developers.google.com/actions/smarthome/traits/mediastate
    """

    name = TRAIT_MEDIA_STATE
    commands: list[str] = []

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
    def supported(domain, features, device_class, _):
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


@register_trait
class ChannelTrait(_Trait):
    """Trait to get media playback state.

    https://developers.google.com/actions/smarthome/traits/channel
    """

    name = TRAIT_CHANNEL
    commands = [COMMAND_SELECT_CHANNEL]

    @staticmethod
    def supported(domain, features, device_class, _):
        """Test if state is supported."""
        if (
            domain == media_player.DOMAIN
            and (features & MediaPlayerEntityFeature.PLAY_MEDIA)
            and device_class == media_player.MediaPlayerDeviceClass.TV
        ):
            return True

        return False

    def sync_attributes(self):
        """Return attributes for a sync request."""
        return {"availableChannels": [], "commandOnlyChannels": True}

    def query_attributes(self):
        """Return channel query attributes."""
        return {}

    async def execute(self, command, data, params, challenge):
        """Execute an setChannel command."""
        if command == COMMAND_SELECT_CHANNEL:
            channel_number = params.get("channelNumber")
        else:
            raise SmartHomeError(ERR_NOT_SUPPORTED, "Unsupported command")

        if not channel_number:
            raise SmartHomeError(
                ERR_NO_AVAILABLE_CHANNEL,
                "Channel is not available",
            )

        await self.hass.services.async_call(
            media_player.DOMAIN,
            media_player.SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: self.state.entity_id,
                media_player.ATTR_MEDIA_CONTENT_ID: channel_number,
                media_player.ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
            },
            blocking=not self.config.should_report_state,
            context=data.context,
        )


@register_trait
class SensorStateTrait(_Trait):
    """Trait to get sensor state.

    https://developers.google.com/actions/smarthome/traits/sensorstate
    """

    sensor_types = {
        sensor.SensorDeviceClass.AQI: ("AirQuality", "AQI"),
        sensor.SensorDeviceClass.CO: ("CarbonMonoxideLevel", "PARTS_PER_MILLION"),
        sensor.SensorDeviceClass.CO2: ("CarbonDioxideLevel", "PARTS_PER_MILLION"),
        sensor.SensorDeviceClass.PM25: ("PM2.5", "MICROGRAMS_PER_CUBIC_METER"),
        sensor.SensorDeviceClass.PM10: ("PM10", "MICROGRAMS_PER_CUBIC_METER"),
        sensor.SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS: (
            "VolatileOrganicCompounds",
            "PARTS_PER_MILLION",
        ),
    }

    name = TRAIT_SENSOR_STATE
    commands: list[str] = []

    def _air_quality_description_for_aqi(self, aqi: float | None) -> str:
        if aqi is None or aqi < 0:
            return "unknown"
        if aqi <= 50:
            return "healthy"
        if aqi <= 100:
            return "moderate"
        if aqi <= 150:
            return "unhealthy for sensitive groups"
        if aqi <= 200:
            return "unhealthy"
        if aqi <= 300:
            return "very unhealthy"

        return "hazardous"

    @classmethod
    def supported(cls, domain, features, device_class, _):
        """Test if state is supported."""
        return domain == sensor.DOMAIN and device_class in cls.sensor_types

    def sync_attributes(self):
        """Return attributes for a sync request."""
        device_class = self.state.attributes.get(ATTR_DEVICE_CLASS)
        data = self.sensor_types.get(device_class)

        if device_class is None or data is None:
            return {}

        sensor_state = {
            "name": data[0],
            "numericCapabilities": {"rawValueUnit": data[1]},
        }

        if device_class == sensor.SensorDeviceClass.AQI:
            sensor_state["descriptiveCapabilities"] = {
                "availableStates": [
                    "healthy",
                    "moderate",
                    "unhealthy for sensitive groups",
                    "unhealthy",
                    "very unhealthy",
                    "hazardous",
                    "unknown",
                ],
            }

        return {"sensorStatesSupported": [sensor_state]}

    def query_attributes(self):
        """Return the attributes of this trait for this entity."""
        device_class = self.state.attributes.get(ATTR_DEVICE_CLASS)
        data = self.sensor_types.get(device_class)

        if device_class is None or data is None:
            return {}

        try:
            value = float(self.state.state)
        except ValueError:
            value = None
        if self.state.state == STATE_UNKNOWN:
            value = None
        sensor_data = {"name": data[0], "rawValue": value}

        if device_class == sensor.SensorDeviceClass.AQI:
            sensor_data["currentSensorState"] = self._air_quality_description_for_aqi(
                value
            )

        return {"currentSensorStateData": [sensor_data]}
