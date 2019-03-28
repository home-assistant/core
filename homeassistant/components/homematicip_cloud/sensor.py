"""Support for HomematicIP Cloud sensors."""
import logging

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE,
    POWER_WATT, TEMP_CELSIUS)

from . import DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematicip_cloud']

ATTR_TEMPERATURE_OFFSET = 'temperature_offset'
ATTR_VALVE_STATE = 'valve_state'
ATTR_VALVE_POSITION = 'valve_position'
ATTR_WIND_DIRECTION = 'wind_direction'
ATTR_WIND_DIRECTION_VARIATION = 'wind_direction_variation_in_degree'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud sensors devices."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HomematicIP Cloud sensors from a config entry."""
    from homematicip.aio.device import (
        AsyncHeatingThermostat, AsyncHeatingThermostatCompact,
        AsyncTemperatureHumiditySensorWithoutDisplay,
        AsyncTemperatureHumiditySensorDisplay, AsyncMotionDetectorIndoor,
        AsyncTemperatureHumiditySensorOutdoor,
        AsyncMotionDetectorPushButton, AsyncLightSensor,
        AsyncPlugableSwitchMeasuring, AsyncBrandSwitchMeasuring,
        AsyncFullFlushSwitchMeasuring, AsyncWeatherSensor,
        AsyncWeatherSensorPlus, AsyncWeatherSensorPro)

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = [HomematicipAccesspointStatus(home)]
    for device in home.devices:
        if isinstance(device, (AsyncHeatingThermostat,
                               AsyncHeatingThermostatCompact)):
            devices.append(HomematicipHeatingThermostat(home, device))
        if isinstance(device, (AsyncTemperatureHumiditySensorDisplay,
                               AsyncTemperatureHumiditySensorWithoutDisplay,
                               AsyncTemperatureHumiditySensorOutdoor,
                               AsyncWeatherSensor,
                               AsyncWeatherSensorPlus,
                               AsyncWeatherSensorPro)):
            devices.append(HomematicipTemperatureSensor(home, device))
            devices.append(HomematicipHumiditySensor(home, device))
        if isinstance(device, (AsyncMotionDetectorIndoor,
                               AsyncMotionDetectorPushButton,
                               AsyncWeatherSensor,
                               AsyncWeatherSensorPlus,
                               AsyncWeatherSensorPro)):
            devices.append(HomematicipIlluminanceSensor(home, device))
        if isinstance(device, AsyncLightSensor):
            devices.append(HomematicipLightSensor(home, device))
        if isinstance(device, (AsyncPlugableSwitchMeasuring,
                               AsyncBrandSwitchMeasuring,
                               AsyncFullFlushSwitchMeasuring)):
            devices.append(HomematicipPowerSensor(home, device))
        if isinstance(device, (AsyncWeatherSensor,
                               AsyncWeatherSensorPlus,
                               AsyncWeatherSensorPro)):
            devices.append(HomematicipWindspeedSensor(home, device))
        if isinstance(device, (AsyncWeatherSensorPlus,
                               AsyncWeatherSensorPro)):
            devices.append(HomematicipTodayRainSensor(home, device))

    if devices:
        async_add_entities(devices)


class HomematicipAccesspointStatus(HomematicipGenericDevice):
    """Representation of an HomeMaticIP Cloud access point."""

    def __init__(self, home):
        """Initialize access point device."""
        super().__init__(home, home)

    @property
    def device_info(self):
        """Return device specific attributes."""
        # Adds a sensor to the existing HAP device
        return {
            'identifiers': {
                # Serial numbers of Homematic IP device
                (HMIPC_DOMAIN, self._device.id)
            }
        }

    @property
    def icon(self):
        """Return the icon of the access point device."""
        return 'mdi:access-point-network'

    @property
    def state(self):
        """Return the state of the access point."""
        return self._home.dutyCycle

    @property
    def available(self):
        """Device available."""
        return self._home.connected

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return '%'


class HomematicipHeatingThermostat(HomematicipGenericDevice):
    """Represenation of a HomematicIP heating thermostat device."""

    def __init__(self, home, device):
        """Initialize heating thermostat device."""
        super().__init__(home, device, 'Heating')

    @property
    def icon(self):
        """Return the icon."""
        from homematicip.base.enums import ValveState

        if super().icon:
            return super().icon
        if self._device.valveState != ValveState.ADAPTION_DONE:
            return 'mdi:alert'
        return 'mdi:radiator'

    @property
    def state(self):
        """Return the state of the radiator valve."""
        from homematicip.base.enums import ValveState

        if self._device.valveState != ValveState.ADAPTION_DONE:
            return self._device.valveState
        return round(self._device.valvePosition*100)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return '%'


class HomematicipHumiditySensor(HomematicipGenericDevice):
    """Represenation of a HomematicIP Cloud humidity device."""

    def __init__(self, home, device):
        """Initialize the thermometer device."""
        super().__init__(home, device, 'Humidity')

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_HUMIDITY

    @property
    def state(self):
        """Return the state."""
        return self._device.humidity

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return '%'


class HomematicipTemperatureSensor(HomematicipGenericDevice):
    """Representation of a HomematicIP Cloud thermometer device."""

    def __init__(self, home, device):
        """Initialize the thermometer device."""
        super().__init__(home, device, 'Temperature')

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def state(self):
        """Return the state."""
        return self._device.actualTemperature

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the windspeed sensor."""
        attr = super().device_state_attributes
        if hasattr(self._device, 'temperatureOffset') and \
                self._device.temperatureOffset:
            attr[ATTR_TEMPERATURE_OFFSET] = self._device.temperatureOffset
        return attr


class HomematicipIlluminanceSensor(HomematicipGenericDevice):
    """Represenation of a HomematicIP Illuminance device."""

    def __init__(self, home, device):
        """Initialize the  device."""
        super().__init__(home, device, 'Illuminance')

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_ILLUMINANCE

    @property
    def state(self):
        """Return the state."""
        return self._device.illumination

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return 'lx'


class HomematicipLightSensor(HomematicipIlluminanceSensor):
    """Represenation of a HomematicIP Illuminance device."""

    @property
    def state(self):
        """Return the state."""
        return self._device.averageIllumination


class HomematicipPowerSensor(HomematicipGenericDevice):
    """Represenation of a HomematicIP power measuring device."""

    def __init__(self, home, device):
        """Initialize the  device."""
        super().__init__(home, device, 'Power')

    @property
    def state(self):
        """Represenation of the HomematicIP power comsumption value."""
        return self._device.currentPowerConsumption

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return POWER_WATT


class HomematicipWindspeedSensor(HomematicipGenericDevice):
    """Represenation of a HomematicIP wind speed sensor."""

    def __init__(self, home, device):
        """Initialize the  device."""
        super().__init__(home, device, 'Windspeed')

    @property
    def state(self):
        """Represenation of the HomematicIP wind speed value."""
        return self._device.windSpeed

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return 'km/h'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the wind speed sensor."""
        attr = super().device_state_attributes
        if hasattr(self._device, 'windDirection') and \
                self._device.windDirection:
            attr[ATTR_WIND_DIRECTION] = \
                _get_wind_direction(self._device.windDirection)
        if hasattr(self._device, 'windDirectionVariation') and \
                self._device.windDirectionVariation:
            attr[ATTR_WIND_DIRECTION_VARIATION] = \
                self._device.windDirectionVariation
        return attr


class HomematicipTodayRainSensor(HomematicipGenericDevice):
    """Represenation of a HomematicIP rain counter of a day sensor."""

    def __init__(self, home, device):
        """Initialize the  device."""
        super().__init__(home, device, 'Today Rain')

    @property
    def state(self):
        """Represenation of the HomematicIP todays rain value."""
        return round(self._device.todayRainCounter, 2)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return 'mm'


def _get_wind_direction(wind_direction_degree):
    """Convert wind direction degree to named direction."""
    if 11.25 <= wind_direction_degree < 33.75:
        return 'NNE'
    if 33.75 <= wind_direction_degree < 56.25:
        return 'NE'
    if 56.25 <= wind_direction_degree < 78.75:
        return 'ENE'
    if 78.75 <= wind_direction_degree < 101.25:
        return 'E'
    if 101.25 <= wind_direction_degree < 123.75:
        return 'ESE'
    if 123.75 <= wind_direction_degree < 146.25:
        return 'SE'
    if 146.25 <= wind_direction_degree < 168.75:
        return 'SSE'
    if 168.75 <= wind_direction_degree < 191.25:
        return 'S'
    if 191.25 <= wind_direction_degree < 213.75:
        return 'SSW'
    if 213.75 <= wind_direction_degree < 236.25:
        return 'SW'
    if 236.25 <= wind_direction_degree < 258.75:
        return 'WSW'
    if 258.75 <= wind_direction_degree < 281.25:
        return 'W'
    if 281.25 <= wind_direction_degree < 303.75:
        return 'WNW'
    if 303.75 <= wind_direction_degree < 326.25:
        return 'NW'
    if 326.25 <= wind_direction_degree < 348.75:
        return 'NNW'
    return 'N'
