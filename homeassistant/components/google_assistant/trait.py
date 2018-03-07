"""Implement the Smart Home traits."""
from homeassistant.components import (
    climate,
    cover,
    group,
    fan,
    media_player,
    light,
    scene,
    script,
    switch,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.util import color as color_util, temperature as temp_util

PREFIX_TRAITS = 'action.devices.traits.'
TRAIT_ONOFF = PREFIX_TRAITS + 'OnOff'
TRAIT_BRIGHTNESS = PREFIX_TRAITS + 'Brightness'
TRAIT_COLOR_SPECTRUM = PREFIX_TRAITS + 'ColorSpectrum'
TRAIT_COLOR_TEMP = PREFIX_TRAITS + 'ColorTemperature'
TRAIT_SCENE = PREFIX_TRAITS + 'Scene'
TRAIT_TEMPERATURE_SETTING = PREFIX_TRAITS + 'TemperatureSetting'

PREFIX_COMMANDS = 'action.devices.commands.'
COMMAND_ONOFF = PREFIX_COMMANDS + 'OnOff'
COMMAND_BRIGHTNESS_ABSOLUTE = PREFIX_COMMANDS + 'BrightnessAbsolute'
COMMAND_COLOR_ABSOLUTE = PREFIX_COMMANDS + 'ColorAbsolute'
COMMAND_ACTIVATE_SCENE = PREFIX_COMMANDS + 'ActivateScene'
COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT = (
    PREFIX_COMMANDS + 'ThermostatTemperatureSetpoint')
COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE = (
    PREFIX_COMMANDS + 'ThermostatTemperatureSetRange')
COMMAND_THERMOSTAT_SET_MODE = PREFIX_COMMANDS + 'ThermostatSetMode'


TRAITS = []


def register_trait(trait):
    """Decorator to register a trait."""
    TRAITS.append(trait)


def _google_temp_unit(state):
    """Return Google temperature unit."""
    if (state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) ==
            TEMP_FAHRENHEIT):
        return 'F'
    return 'C'


class _Trait:
    """Represents a Trait inside Google Assistant skill."""

    commands = []

    def __init__(self, state):
        """Initialize a trait for a state."""
        self.state = state

    def sync_attributes(self):
        """Return attributes for a sync request."""
        raise NotImplementedError

    def query_attributes(self):
        """Return the attributes of this trait for this entity."""
        raise NotImplementedError

    def can_execute(self, command, params):
        """Test if command can be executed."""
        return command in self.commands

    async def execute(self, hass, command, params):
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
    def supported(domain, features, unit):
        """Test if state is supported."""
        if domain == light.DOMAIN:
            return features & light.SUPPORT_BRIGHTNESS
        elif domain == cover.DOMAIN:
            return features & cover.SUPPORT_SET_POSITION
        elif domain == media_player.DOMAIN:
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
                response['brightness'] = int(100 * (brightness / 255))

        elif domain == media_player.DOMAIN:
            level = self.state.attributes.get(
                media_player.ATTR_MEDIA_VOLUME_LEVEL)
            if level is not None:
                # Convert 0.0-1.0 to 0-255
                response['brightness'] = int(level * 100)

        return response

    async def execute(self, hass, command, params):
        """Execute a brightness command."""
        domain = self.state.domain

        if domain == light.DOMAIN:
            await hass.services.async_call(
                light.DOMAIN, light.SERVICE_TURN_ON, {
                    light.ATTR_BRIGHTNESS_PCT: params['brightness']
                })
        elif domain == cover.DOMAIN:
            await hass.services.async_call(
                cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION, {
                    cover.ATTR_POSITION: params['brightness']
                })
        elif domain == media_player.DOMAIN:
            await hass.services.async_call(
                media_player.DOMAIN, media_player.SERVICE_VOLUME_SET, {
                    media_player.ATTR_MEDIA_VOLUME_LEVEL:
                    params['brightness'] / 100
                })


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
    def supported(domain, features, unit):
        """Test if state is supported."""
        return domain in (
            group.DOMAIN,
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
        state = self.state
        domain = state.domain
        response = {}

        if domain == cover.DOMAIN:
            response['on'] = state.state != cover.STATE_CLOSED
        else:
            response['on'] = state.state != STATE_OFF

        return response

    async def execute(self, hass, command, params):
        """Execute an OnOff command."""
        domain = self.state.domain

        if domain == cover.DOMAIN:
            service_domain = domain
            if params['on']:
                service = cover.SERVICE_OPEN_COVER
            else:
                service = cover.SERVICE_CLOSE_COVER

        elif domain == group.DOMAIN:
            service_domain = 'homeassisatnt'
            service = SERVICE_TURN_ON

        else:
            service_domain = domain
            service = SERVICE_TURN_ON if params['on'] else SERVICE_TURN_OFF

        await hass.services.async_call(service_domain, service, {
            ATTR_ENTITY_ID: self.state.entity_id
        })


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
    def supported(domain, features, unit):
        """Test if state is supported."""
        if domain != light.DOMAIN:
            return False

        return features & (light.SUPPORT_RGB_COLOR | light.SUPPORT_XY_COLOR)

    def sync_attributes(self):
        """Return color spectrum attributes for a sync request."""
        # Other colorModel is hsv
        return {'colorModel': 'rgb'}

    def query_attributes(self):
        """Return color spectrum query attributes."""
        response = {}

        # No need to handle XY color because light component will always
        # convert XY to RGB if possible (which is when brightness is available)
        color_rgb = self.state.attributes.get(light.ATTR_RGB_COLOR)
        if color_rgb is not None:
            response['color'] = {
                'spectrumRGB': int(color_util.color_rgb_to_hex(
                    color_rgb[0], color_rgb[1], color_rgb[2]), 16),
            }

        return response

    def can_execute(self, command, params):
        """Test if command can be executed."""
        return command in self.commands and 'color' in params

    async def execute(self, hass, command, params):
        """Execute a color spectrum command."""
        hex_value = "{0:x}".format(params['color']['spectrumRGB']).zfill(6)
        color = color_util.rgb_hex_to_rgb_list(hex_value)

        await hass.services.async_call(light.DOMAIN, SERVICE_TURN_ON, {
            ATTR_ENTITY_ID: self.state.entity_id,
            light.ATTR_RGB_COLOR: color
        })


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
    def supported(domain, features, unit):
        """Test if state is supported."""
        if domain != light.DOMAIN:
            return

        return features & light.SUPPORT_COLOR_TEMP

    def sync_attributes(self):
        """Return color temperature attributes for a sync request."""
        attrs = self.state.attributes
        return {
            'temperatureMinK': color_util.color_temperature_mired_to_kelvin(
                attrs.get(light.ATTR_MIN_MIREDS)),
            'temperatureMaxK': color_util.color_temperature_mired_to_kelvin(
                attrs.get(light.ATTR_MAX_MIREDS)),
        }

    def query_attributes(self):
        """Return color temperature query attributes."""
        response = {}

        temp = self.state.attributes.get(light.ATTR_COLOR_TEMP)
        if temp is not None:
            response['color'] = {
                'temperature':
                    color_util.color_temperature_mired_to_kelvin(temp)
            }

        return response

    def can_execute(self, command, params):
        """Test if command can be executed."""
        return command in self.commands and 'temperature' in params

    async def execute(self, hass, command, params):
        """Execute a color temperature command."""
        await hass.services.async_call(light.DOMAIN, SERVICE_TURN_ON, {
            ATTR_ENTITY_ID: self.state.entity_id,
            light.ATTR_KELVIN: params['color']['temperature'],
        })


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
    def supported(domain, features, unit):
        """Test if state is supported."""
        return domain in (scene.DOMAIN, script.DOMAIN)

    def sync_attributes(self):
        """Return scene attributes for a sync request."""
        # Neither supported domain can support sceneReversible
        return {}

    def query_attributes(self):
        """Return scene query attributes."""
        return {}

    async def execute(self, hass, command, params):
        """Execute a scene command."""
        await hass.services.async_call(self.state.domain, SERVICE_TURN_ON, {
            ATTR_ENTITY_ID: self.state.entity_id
        })


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
    hass_to_google = {
        climate.STATE_HEAT: 'heat',
        climate.STATE_COOL: 'cool',
        climate.STATE_OFF: 'off',
        climate.STATE_ON: 'on',
        climate.STATE_AUTO: 'heatcool',
    }
    google_to_hass = {value: key for key, value in hass_to_google.items()}

    @staticmethod
    def supported(domain, features, unit):
        """Test if state is supported."""
        return domain == climate.DOMAIN

    def sync_attributes(self):
        """Return temperature point and modes attributes for a sync request."""
        modes = []
        for mode in self.state.attributes.get(climate.ATTR_OPERATION_LIST, []):
            google_mode = self.hass_to_google.get(mode)
            if google_mode is not None:
                modes.append(google_mode)

        return {
            'availableThermostatModes': ','.join(modes),
            'thermostatTemperatureUnit': _google_temp_unit(self.state),
        }

    def query_attributes(self):
        """Return temperature point and modes query attributes."""
        attrs = self.state.attributes
        response = {}

        operation = attrs.get(climate.ATTR_OPERATION_MODE)
        if operation is not None and operation in self.hass_to_google:
            response['thermostatMode'] = self.hass_to_google[operation]

        unit = self.state.attributes[ATTR_UNIT_OF_MEASUREMENT]

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

    async def execute(self, hass, command, params):
        """Execute a temperature point or mode command."""
        # All sent in temperatures are always in Celsius
        unit = self.state.attributes[ATTR_UNIT_OF_MEASUREMENT]

        if command == COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT:
            await hass.services.async_call(
                climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE, {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    climate.ATTR_TEMPERATURE: temp_util.convert(
                        params['thermostatTemperatureSetpoint'], TEMP_CELSIUS,
                        unit)
                })

        elif command == COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE:
            await hass.services.async_call(
                climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE, {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    climate.ATTR_TARGET_TEMP_HIGH: temp_util.convert(
                        params['thermostatTemperatureSetpointHigh'],
                        TEMP_CELSIUS, unit),
                    climate.ATTR_TARGET_TEMP_LOW: temp_util.convert(
                        params['thermostatTemperatureSetpointLow'],
                        TEMP_CELSIUS, unit),
                })

        elif command == COMMAND_THERMOSTAT_SET_MODE:
            await hass.services.async_call(
                climate.DOMAIN, climate.SERVICE_SET_OPERATION_MODE, {
                    ATTR_ENTITY_ID: self.state.entity_id,
                    climate.ATTR_OPERATION_MODE:
                        self.google_to_hass[params['thermostatMode']],
                })
