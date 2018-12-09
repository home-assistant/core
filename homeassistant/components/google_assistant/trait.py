"""Implement the Smart Home traits."""
import logging

from homeassistant.components import (
    climate,
    cover,
    group,
    fan,
    input_boolean,
    media_player,
    light,
    lock,
    scene,
    script,
    switch,
    vacuum,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_LOCKED,
    STATE_OFF,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    ATTR_SUPPORTED_FEATURES,
)
from homeassistant.core import DOMAIN as HA_DOMAIN
from homeassistant.util import color as color_util, temperature as temp_util
from .const import ERR_VALUE_OUT_OF_RANGE
from .helpers import SmartHomeError

_LOGGER = logging.getLogger(__name__)

PREFIX_TRAITS = 'action.devices.traits.'
TRAIT_ONOFF = PREFIX_TRAITS + 'OnOff'
TRAIT_DOCK = PREFIX_TRAITS + 'Dock'
TRAIT_STARTSTOP = PREFIX_TRAITS + 'StartStop'
TRAIT_BRIGHTNESS = PREFIX_TRAITS + 'Brightness'
TRAIT_COLOR_SPECTRUM = PREFIX_TRAITS + 'ColorSpectrum'
TRAIT_COLOR_TEMP = PREFIX_TRAITS + 'ColorTemperature'
TRAIT_SCENE = PREFIX_TRAITS + 'Scene'
TRAIT_TEMPERATURE_SETTING = PREFIX_TRAITS + 'TemperatureSetting'
TRAIT_LOCKUNLOCK = PREFIX_TRAITS + 'LockUnlock'
TRAIT_FANSPEED = PREFIX_TRAITS + 'FanSpeed'
TRAIT_MODES = PREFIX_TRAITS + 'Modes'

PREFIX_COMMANDS = 'action.devices.commands.'
COMMAND_ONOFF = PREFIX_COMMANDS + 'OnOff'
COMMAND_DOCK = PREFIX_COMMANDS + 'Dock'
COMMAND_STARTSTOP = PREFIX_COMMANDS + 'StartStop'
COMMAND_PAUSEUNPAUSE = PREFIX_COMMANDS + 'PauseUnpause'
COMMAND_BRIGHTNESS_ABSOLUTE = PREFIX_COMMANDS + 'BrightnessAbsolute'
COMMAND_COLOR_ABSOLUTE = PREFIX_COMMANDS + 'ColorAbsolute'
COMMAND_ACTIVATE_SCENE = PREFIX_COMMANDS + 'ActivateScene'
COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT = (
    PREFIX_COMMANDS + 'ThermostatTemperatureSetpoint')
COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE = (
    PREFIX_COMMANDS + 'ThermostatTemperatureSetRange')
COMMAND_THERMOSTAT_SET_MODE = PREFIX_COMMANDS + 'ThermostatSetMode'
COMMAND_LOCKUNLOCK = PREFIX_COMMANDS + 'LockUnlock'
COMMAND_FANSPEED = PREFIX_COMMANDS + 'SetFanSpeed'
COMMAND_MODES = PREFIX_COMMANDS + 'SetModes'

TRAITS = []


def register_trait(trait):
    """Decorate a function to register a trait."""
    TRAITS.append(trait)
    return trait


def _google_temp_unit(units):
    """Return Google temperature unit."""
    if units == TEMP_FAHRENHEIT:
        return 'F'
    return 'C'


class _Trait:
    """Represents a Trait inside Google Assistant skill."""

    commands = []

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

    async def execute(self, command, params):
        """Execute a trait command."""
        raise NotImplementedError


@register_trait
class BrightnessTrait(_Trait):
    """Trait to control brightness of a device.

    https://developers.google.com/actions/smarthome/traits/brightness
    """

    name = TRAIT_BRIGHTNESS
    commands = [
        COMMAND_BRIGHTNESS_ABSOLUTE
    ]

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        if domain == light.DOMAIN:
            return features & light.SUPPORT_BRIGHTNESS
        if domain == cover.DOMAIN:
            return features & cover.SUPPORT_SET_POSITION
        if domain == media_player.DOMAIN:
            return features & media_player.SUPPORT_VOLUME_SET

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
                response['brightness'] = int(100 * (brightness / 255))

        elif domain == cover.DOMAIN:
            position = self.state.attributes.get(cover.ATTR_CURRENT_POSITION)
            if position is not None:
                response['brightness'] = position

        elif domain == media_player.DOMAIN:
            level = self.state.attributes.get(
                media_player.ATTR_MEDIA_VOLUME_LEVEL)
            if level is not None:
                # Convert 0.0-1.0 to 0-255
                response['brightness'] = int(level * 100)

        return response

    async def execute(self, command, params):
        """Execute a brightness command."""
        domain = self.state.domain

        if domain == light.DOMAIN:
            await self.hass.services.async_call(
                light.DOMAIN, light.SERVICE_TURN_ON, {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    light.ATTR_BRIGHTNESS_PCT: params['brightness']
                }, blocking=True)
        elif domain == cover.DOMAIN:
            await self.hass.services.async_call(
                cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION, {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    cover.ATTR_POSITION: params['brightness']
                }, blocking=True)
        elif domain == media_player.DOMAIN:
            await self.hass.services.async_call(
                media_player.DOMAIN, media_player.SERVICE_VOLUME_SET, {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    media_player.ATTR_MEDIA_VOLUME_LEVEL:
                    params['brightness'] / 100
                }, blocking=True)


@register_trait
class OnOffTrait(_Trait):
    """Trait to offer basic on and off functionality.

    https://developers.google.com/actions/smarthome/traits/onoff
    """

    name = TRAIT_ONOFF
    commands = [
        COMMAND_ONOFF
    ]

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        if domain == climate.DOMAIN:
            return features & climate.SUPPORT_ON_OFF != 0
        return domain in (
            group.DOMAIN,
            input_boolean.DOMAIN,
            switch.DOMAIN,
            fan.DOMAIN,
            light.DOMAIN,
            cover.DOMAIN,
            media_player.DOMAIN,
        )

    def sync_attributes(self):
        """Return OnOff attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return OnOff query attributes."""
        if self.state.domain == cover.DOMAIN:
            return {'on': self.state.state != cover.STATE_CLOSED}
        return {'on': self.state.state != STATE_OFF}

    async def execute(self, command, params):
        """Execute an OnOff command."""
        domain = self.state.domain

        if domain == cover.DOMAIN:
            service_domain = domain
            if params['on']:
                service = cover.SERVICE_OPEN_COVER
            else:
                service = cover.SERVICE_CLOSE_COVER

        elif domain == group.DOMAIN:
            service_domain = HA_DOMAIN
            service = SERVICE_TURN_ON if params['on'] else SERVICE_TURN_OFF

        else:
            service_domain = domain
            service = SERVICE_TURN_ON if params['on'] else SERVICE_TURN_OFF

        await self.hass.services.async_call(service_domain, service, {
            ATTR_ENTITY_ID: self.state.entity_id
        }, blocking=True)


@register_trait
class ColorSpectrumTrait(_Trait):
    """Trait to offer color spectrum functionality.

    https://developers.google.com/actions/smarthome/traits/colorspectrum
    """

    name = TRAIT_COLOR_SPECTRUM
    commands = [
        COMMAND_COLOR_ABSOLUTE
    ]

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        if domain != light.DOMAIN:
            return False

        return features & light.SUPPORT_COLOR

    def sync_attributes(self):
        """Return color spectrum attributes for a sync request."""
        # Other colorModel is hsv
        return {'colorModel': 'rgb'}

    def query_attributes(self):
        """Return color spectrum query attributes."""
        response = {}

        color_hs = self.state.attributes.get(light.ATTR_HS_COLOR)
        if color_hs is not None:
            response['color'] = {
                'spectrumRGB': int(color_util.color_rgb_to_hex(
                    *color_util.color_hs_to_RGB(*color_hs)), 16),
            }

        return response

    def can_execute(self, command, params):
        """Test if command can be executed."""
        return (command in self.commands and
                'spectrumRGB' in params.get('color', {}))

    async def execute(self, command, params):
        """Execute a color spectrum command."""
        # Convert integer to hex format and left pad with 0's till length 6
        hex_value = "{0:06x}".format(params['color']['spectrumRGB'])
        color = color_util.color_RGB_to_hs(
            *color_util.rgb_hex_to_rgb_list(hex_value))

        await self.hass.services.async_call(light.DOMAIN, SERVICE_TURN_ON, {
            ATTR_ENTITY_ID: self.state.entity_id,
            light.ATTR_HS_COLOR: color
        }, blocking=True)


@register_trait
class ColorTemperatureTrait(_Trait):
    """Trait to offer color temperature functionality.

    https://developers.google.com/actions/smarthome/traits/colortemperature
    """

    name = TRAIT_COLOR_TEMP
    commands = [
        COMMAND_COLOR_ABSOLUTE
    ]

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        if domain != light.DOMAIN:
            return False

        return features & light.SUPPORT_COLOR_TEMP

    def sync_attributes(self):
        """Return color temperature attributes for a sync request."""
        attrs = self.state.attributes
        # Max Kelvin is Min Mireds K = 1000000 / mireds
        # Min Kevin is Max Mireds K = 1000000 / mireds
        return {
            'temperatureMaxK': color_util.color_temperature_mired_to_kelvin(
                attrs.get(light.ATTR_MIN_MIREDS)),
            'temperatureMinK': color_util.color_temperature_mired_to_kelvin(
                attrs.get(light.ATTR_MAX_MIREDS)),
        }

    def query_attributes(self):
        """Return color temperature query attributes."""
        response = {}

        temp = self.state.attributes.get(light.ATTR_COLOR_TEMP)
        # Some faulty integrations might put 0 in here, raising exception.
        if temp == 0:
            _LOGGER.warning('Entity %s has incorrect color temperature %s',
                            self.state.entity_id, temp)
        elif temp is not None:
            response['color'] = {
                'temperature':
                    color_util.color_temperature_mired_to_kelvin(temp)
            }

        return response

    def can_execute(self, command, params):
        """Test if command can be executed."""
        return (command in self.commands and
                'temperature' in params.get('color', {}))

    async def execute(self, command, params):
        """Execute a color temperature command."""
        temp = color_util.color_temperature_kelvin_to_mired(
            params['color']['temperature'])
        min_temp = self.state.attributes[light.ATTR_MIN_MIREDS]
        max_temp = self.state.attributes[light.ATTR_MAX_MIREDS]

        if temp < min_temp or temp > max_temp:
            raise SmartHomeError(
                ERR_VALUE_OUT_OF_RANGE,
                "Temperature should be between {} and {}".format(min_temp,
                                                                 max_temp))

        await self.hass.services.async_call(light.DOMAIN, SERVICE_TURN_ON, {
            ATTR_ENTITY_ID: self.state.entity_id,
            light.ATTR_COLOR_TEMP: temp,
        }, blocking=True)


@register_trait
class SceneTrait(_Trait):
    """Trait to offer scene functionality.

    https://developers.google.com/actions/smarthome/traits/scene
    """

    name = TRAIT_SCENE
    commands = [
        COMMAND_ACTIVATE_SCENE
    ]

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        return domain in (scene.DOMAIN, script.DOMAIN)

    def sync_attributes(self):
        """Return scene attributes for a sync request."""
        # Neither supported domain can support sceneReversible
        return {}

    def query_attributes(self):
        """Return scene query attributes."""
        return {}

    async def execute(self, command, params):
        """Execute a scene command."""
        # Don't block for scripts as they can be slow.
        await self.hass.services.async_call(
            self.state.domain, SERVICE_TURN_ON, {
                ATTR_ENTITY_ID: self.state.entity_id
            }, blocking=self.state.domain != script.DOMAIN)


@register_trait
class DockTrait(_Trait):
    """Trait to offer dock functionality.

    https://developers.google.com/actions/smarthome/traits/dock
    """

    name = TRAIT_DOCK
    commands = [
        COMMAND_DOCK
    ]

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        return domain == vacuum.DOMAIN

    def sync_attributes(self):
        """Return dock attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return dock query attributes."""
        return {'isDocked': self.state.state == vacuum.STATE_DOCKED}

    async def execute(self, command, params):
        """Execute a dock command."""
        await self.hass.services.async_call(
            self.state.domain, vacuum.SERVICE_RETURN_TO_BASE, {
                ATTR_ENTITY_ID: self.state.entity_id
            }, blocking=True)


@register_trait
class StartStopTrait(_Trait):
    """Trait to offer StartStop functionality.

    https://developers.google.com/actions/smarthome/traits/startstop
    """

    name = TRAIT_STARTSTOP
    commands = [
        COMMAND_STARTSTOP,
        COMMAND_PAUSEUNPAUSE
    ]

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        return domain == vacuum.DOMAIN

    def sync_attributes(self):
        """Return StartStop attributes for a sync request."""
        return {'pausable':
                self.state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
                & vacuum.SUPPORT_PAUSE != 0}

    def query_attributes(self):
        """Return StartStop query attributes."""
        return {
            'isRunning': self.state.state == vacuum.STATE_CLEANING,
            'isPaused': self.state.state == vacuum.STATE_PAUSED,
        }

    async def execute(self, command, params):
        """Execute a StartStop command."""
        if command == COMMAND_STARTSTOP:
            if params['start']:
                await self.hass.services.async_call(
                    self.state.domain, vacuum.SERVICE_START, {
                        ATTR_ENTITY_ID: self.state.entity_id
                    }, blocking=True)
            else:
                await self.hass.services.async_call(
                    self.state.domain, vacuum.SERVICE_STOP, {
                        ATTR_ENTITY_ID: self.state.entity_id
                    }, blocking=True)
        elif command == COMMAND_PAUSEUNPAUSE:
            if params['pause']:
                await self.hass.services.async_call(
                    self.state.domain, vacuum.SERVICE_PAUSE, {
                        ATTR_ENTITY_ID: self.state.entity_id
                    }, blocking=True)
            else:
                await self.hass.services.async_call(
                    self.state.domain, vacuum.SERVICE_START, {
                        ATTR_ENTITY_ID: self.state.entity_id
                    }, blocking=True)


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
    hass_to_google = {
        climate.STATE_HEAT: 'heat',
        climate.STATE_COOL: 'cool',
        climate.STATE_OFF: 'off',
        climate.STATE_AUTO: 'heatcool',
    }
    google_to_hass = {value: key for key, value in hass_to_google.items()}

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        if domain != climate.DOMAIN:
            return False

        return features & climate.SUPPORT_OPERATION_MODE

    def sync_attributes(self):
        """Return temperature point and modes attributes for a sync request."""
        modes = []
        for mode in self.state.attributes.get(climate.ATTR_OPERATION_LIST, []):
            google_mode = self.hass_to_google.get(mode)
            if google_mode is not None:
                modes.append(google_mode)

        return {
            'availableThermostatModes': ','.join(modes),
            'thermostatTemperatureUnit': _google_temp_unit(
                self.hass.config.units.temperature_unit)
        }

    def query_attributes(self):
        """Return temperature point and modes query attributes."""
        attrs = self.state.attributes
        response = {}

        operation = attrs.get(climate.ATTR_OPERATION_MODE)
        if operation is not None and operation in self.hass_to_google:
            response['thermostatMode'] = self.hass_to_google[operation]

        unit = self.hass.config.units.temperature_unit

        current_temp = attrs.get(climate.ATTR_CURRENT_TEMPERATURE)
        if current_temp is not None:
            response['thermostatTemperatureAmbient'] = \
                round(temp_util.convert(current_temp, unit, TEMP_CELSIUS), 1)

        current_humidity = attrs.get(climate.ATTR_CURRENT_HUMIDITY)
        if current_humidity is not None:
            response['thermostatHumidityAmbient'] = current_humidity

        if (operation == climate.STATE_AUTO and
                climate.ATTR_TARGET_TEMP_HIGH in attrs and
                climate.ATTR_TARGET_TEMP_LOW in attrs):
            response['thermostatTemperatureSetpointHigh'] = \
                round(temp_util.convert(attrs[climate.ATTR_TARGET_TEMP_HIGH],
                                        unit, TEMP_CELSIUS), 1)
            response['thermostatTemperatureSetpointLow'] = \
                round(temp_util.convert(attrs[climate.ATTR_TARGET_TEMP_LOW],
                                        unit, TEMP_CELSIUS), 1)
        else:
            target_temp = attrs.get(climate.ATTR_TEMPERATURE)
            if target_temp is not None:
                response['thermostatTemperatureSetpoint'] = round(
                    temp_util.convert(target_temp, unit, TEMP_CELSIUS), 1)

        return response

    async def execute(self, command, params):
        """Execute a temperature point or mode command."""
        # All sent in temperatures are always in Celsius
        unit = self.hass.config.units.temperature_unit
        min_temp = self.state.attributes[climate.ATTR_MIN_TEMP]
        max_temp = self.state.attributes[climate.ATTR_MAX_TEMP]

        if command == COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT:
            temp = temp_util.convert(params['thermostatTemperatureSetpoint'],
                                     TEMP_CELSIUS, unit)

            if temp < min_temp or temp > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    "Temperature should be between {} and {}".format(min_temp,
                                                                     max_temp))

            await self.hass.services.async_call(
                climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE, {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    climate.ATTR_TEMPERATURE: temp
                }, blocking=True)

        elif command == COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE:
            temp_high = temp_util.convert(
                params['thermostatTemperatureSetpointHigh'], TEMP_CELSIUS,
                unit)

            if temp_high < min_temp or temp_high > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    "Upper bound for temperature range should be between "
                    "{} and {}".format(min_temp, max_temp))

            temp_low = temp_util.convert(
                params['thermostatTemperatureSetpointLow'], TEMP_CELSIUS, unit)

            if temp_low < min_temp or temp_low > max_temp:
                raise SmartHomeError(
                    ERR_VALUE_OUT_OF_RANGE,
                    "Lower bound for temperature range should be between "
                    "{} and {}".format(min_temp, max_temp))

            await self.hass.services.async_call(
                climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE, {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    climate.ATTR_TARGET_TEMP_HIGH: temp_high,
                    climate.ATTR_TARGET_TEMP_LOW: temp_low,
                }, blocking=True)

        elif command == COMMAND_THERMOSTAT_SET_MODE:
            await self.hass.services.async_call(
                climate.DOMAIN, climate.SERVICE_SET_OPERATION_MODE, {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    climate.ATTR_OPERATION_MODE:
                        self.google_to_hass[params['thermostatMode']],
                }, blocking=True)


@register_trait
class LockUnlockTrait(_Trait):
    """Trait to lock or unlock a lock.

    https://developers.google.com/actions/smarthome/traits/lockunlock
    """

    name = TRAIT_LOCKUNLOCK
    commands = [
        COMMAND_LOCKUNLOCK
    ]

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        return domain == lock.DOMAIN

    def sync_attributes(self):
        """Return LockUnlock attributes for a sync request."""
        return {}

    def query_attributes(self):
        """Return LockUnlock query attributes."""
        return {'isLocked': self.state.state == STATE_LOCKED}

    def can_execute(self, command, params):
        """Test if command can be executed."""
        allowed_unlock = not params['lock'] and self.config.allow_unlock
        return params['lock'] or allowed_unlock

    async def execute(self, command, params):
        """Execute an LockUnlock command."""
        if params['lock']:
            service = lock.SERVICE_LOCK
        else:
            service = lock.SERVICE_UNLOCK

        await self.hass.services.async_call(lock.DOMAIN, service, {
            ATTR_ENTITY_ID: self.state.entity_id
        }, blocking=True)


@register_trait
class FanSpeedTrait(_Trait):
    """Trait to control speed of Fan.

    https://developers.google.com/actions/smarthome/traits/fanspeed
    """

    name = TRAIT_FANSPEED
    commands = [
        COMMAND_FANSPEED
    ]

    speed_synonyms = {
        fan.SPEED_OFF: ['stop', 'off'],
        fan.SPEED_LOW: ['slow', 'low', 'slowest', 'lowest'],
        fan.SPEED_MEDIUM: ['medium', 'mid', 'middle'],
        fan.SPEED_HIGH: [
            'high', 'max', 'fast', 'highest', 'fastest', 'maximum'
        ]
    }

    @staticmethod
    def supported(domain, features):
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
                "speed_values": [{
                    "speed_synonym": self.speed_synonyms.get(mode),
                    "lang": 'en'
                }]
            }
            speeds.append(speed)

        return {
            'availableFanSpeeds': {
                'speeds': speeds,
                'ordered': True
            },
            "reversible": bool(self.state.attributes.get(
                ATTR_SUPPORTED_FEATURES, 0) & fan.SUPPORT_DIRECTION)
        }

    def query_attributes(self):
        """Return speed point and modes query attributes."""
        attrs = self.state.attributes
        response = {}

        speed = attrs.get(fan.ATTR_SPEED)
        if speed is not None:
            response['on'] = speed != fan.SPEED_OFF
            response['online'] = True
            response['currentFanSpeedSetting'] = speed

        return response

    async def execute(self, command, params):
        """Execute an SetFanSpeed command."""
        await self.hass.services.async_call(
            fan.DOMAIN, fan.SERVICE_SET_SPEED, {
                ATTR_ENTITY_ID: self.state.entity_id,
                fan.ATTR_SPEED: params['fanSpeed']
            }, blocking=True)


@register_trait
class ModesTrait(_Trait):
    """Trait to set modes.

    https://developers.google.com/actions/smarthome/traits/modes
    """

    name = TRAIT_MODES
    commands = [
        COMMAND_MODES
    ]

    # Google requires specific mode names and settings. Here is the full list.
    # https://developers.google.com/actions/reference/smarthome/traits/modes
    # All settings are mapped here as of 2018-11-28 and can be used for other
    # entity types.

    HA_TO_GOOGLE = {
        media_player.ATTR_INPUT_SOURCE: "input source",
    }
    SUPPORTED_MODE_SETTINGS = {
        'xsmall': [
            'xsmall', 'extra small', 'min', 'minimum', 'tiny', 'xs'],
        'small': ['small', 'half'],
        'large': ['large', 'big', 'full'],
        'xlarge': ['extra large', 'xlarge', 'xl'],
        'Cool': ['cool', 'rapid cool', 'rapid cooling'],
        'Heat': ['heat'], 'Low': ['low'],
        'Medium': ['medium', 'med', 'mid', 'half'],
        'High': ['high'],
        'Auto': ['auto', 'automatic'],
        'Bake': ['bake'], 'Roast': ['roast'],
        'Convection Bake': ['convection bake', 'convect bake'],
        'Convection Roast': ['convection roast', 'convect roast'],
        'Favorite': ['favorite'],
        'Broil': ['broil'],
        'Warm': ['warm'],
        'Off': ['off'],
        'On': ['on'],
        'Normal': [
            'normal', 'normal mode', 'normal setting', 'standard',
            'schedule', 'original', 'default', 'old settings'
        ],
        'None': ['none'],
        'Tap Cold': ['tap cold'],
        'Cold Warm': ['cold warm'],
        'Hot': ['hot'],
        'Extra Hot': ['extra hot'],
        'Eco': ['eco'],
        'Wool': ['wool', 'fleece'],
        'Turbo': ['turbo'],
        'Rinse': ['rinse', 'rinsing', 'rinse wash'],
        'Away': ['away', 'holiday'],
        'maximum': ['maximum'],
        'media player': ['media player'],
        'chromecast': ['chromecast'],
        'tv': [
            'tv', 'television', 'tv position', 'television position',
            'watching tv', 'watching tv position', 'entertainment',
            'entertainment position'
        ],
        'am fm': ['am fm', 'am radio', 'fm radio'],
        'internet radio': ['internet radio'],
        'satellite': ['satellite'],
        'game console': ['game console'],
        'antifrost': ['antifrost', 'anti-frost'],
        'boost': ['boost'],
        'Clock': ['clock'],
        'Message': ['message'],
        'Messages': ['messages'],
        'News': ['news'],
        'Disco': ['disco'],
        'antifreeze': ['antifreeze', 'anti-freeze', 'anti freeze'],
        'balanced': ['balanced', 'normal'],
        'swing': ['swing'],
        'media': ['media', 'media mode'],
        'panic': ['panic'],
        'ring': ['ring'],
        'frozen': ['frozen', 'rapid frozen', 'rapid freeze'],
        'cotton': ['cotton', 'cottons'],
        'blend': ['blend', 'mix'],
        'baby wash': ['baby wash'],
        'synthetics': ['synthetic', 'synthetics', 'compose'],
        'hygiene': ['hygiene', 'sterilization'],
        'smart': ['smart', 'intelligent', 'intelligence'],
        'comfortable': ['comfortable', 'comfort'],
        'manual': ['manual'],
        'energy saving': ['energy saving'],
        'sleep': ['sleep'],
        'quick wash': ['quick wash', 'fast wash'],
        'cold': ['cold'],
        'airsupply': ['airsupply', 'air supply'],
        'dehumidification': ['dehumidication', 'dehumidify'],
        'game': ['game', 'game mode']
    }

    @staticmethod
    def supported(domain, features):
        """Test if state is supported."""
        if domain != media_player.DOMAIN:
            return False

        return features & media_player.SUPPORT_SELECT_SOURCE

    def sync_attributes(self):
        """Return mode attributes for a sync request."""
        sources_list = self.state.attributes.get(
            media_player.ATTR_INPUT_SOURCE_LIST, [])
        modes = []
        sources = {}

        if sources_list:
            sources = {
                "name": self.HA_TO_GOOGLE.get(media_player.ATTR_INPUT_SOURCE),
                "name_values": [{
                    "name_synonym": ['input source'],
                    "lang": "en"
                }],
                "settings": [],
                "ordered": False
            }
            for source in sources_list:
                if source in self.SUPPORTED_MODE_SETTINGS:
                    src = source
                    synonyms = self.SUPPORTED_MODE_SETTINGS.get(src)
                elif source.lower() in self.SUPPORTED_MODE_SETTINGS:
                    src = source.lower()
                    synonyms = self.SUPPORTED_MODE_SETTINGS.get(src)

                else:
                    continue

                sources['settings'].append(
                    {
                        "setting_name": src,
                        "setting_values": [{
                            "setting_synonym": synonyms,
                            "lang": "en"
                        }]
                    }
                )
        if sources:
            modes.append(sources)
        payload = {'availableModes': modes}

        return payload

    def query_attributes(self):
        """Return current modes."""
        attrs = self.state.attributes
        response = {}
        mode_settings = {}

        if attrs.get(media_player.ATTR_INPUT_SOURCE_LIST):
            mode_settings.update({
                media_player.ATTR_INPUT_SOURCE: attrs.get(
                    media_player.ATTR_INPUT_SOURCE)
            })
        if mode_settings:
            response['on'] = self.state.state != STATE_OFF
            response['online'] = True
            response['currentModeSettings'] = mode_settings

        return response

    async def execute(self, command, params):
        """Execute an SetModes command."""
        settings = params.get('updateModeSettings')
        requested_source = settings.get(
            self.HA_TO_GOOGLE.get(media_player.ATTR_INPUT_SOURCE))

        if requested_source:
            for src in self.state.attributes.get(
                    media_player.ATTR_INPUT_SOURCE_LIST):
                if src.lower() == requested_source.lower():
                    source = src

                    await self.hass.services.async_call(
                        media_player.DOMAIN,
                        media_player.SERVICE_SELECT_SOURCE, {
                            ATTR_ENTITY_ID: self.state.entity_id,
                            media_player.ATTR_INPUT_SOURCE: source
                        }, blocking=True)
