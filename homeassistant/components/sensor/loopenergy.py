"""
Support for Loop Energy sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.loop_energy/
"""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.util import convert

_LOGGER = logging.getLogger(__name__)

DOMAIN = "loopenergy"

REQUIREMENTS = ['pyloopenergy==0.0.12']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Loop Energy sensors."""
    import pyloopenergy

    elec_serial = config.get('electricity_serial')
    elec_secret = config.get('electricity_secret')
    gas_serial = config.get('gas_serial')
    gas_secret = config.get('gas_secret')
    gas_type = config.get('gas_type', 'metric')
    gas_calorific = convert(config.get('gas_calorific'), float, 39.11)

    if not (elec_serial and elec_secret):
        _LOGGER.error(
            "Configuration Error, "
            "please make sure you have configured electricity "
            "serial and secret tokens")
        return None

    if (gas_serial or gas_secret) and not (gas_serial and gas_secret):
        _LOGGER.error(
            "Configuration Error, "
            "please make sure you have configured gas "
            "serial and secret tokens")
        return None

    if gas_type not in ['imperial', 'metric']:
        _LOGGER.error(
            "Configuration Error, 'gas_type' "
            "can only be 'imperial' or 'metric' ")
        return None

    # pylint: disable=too-many-function-args
    controller = pyloopenergy.LoopEnergy(
        elec_serial,
        elec_secret,
        gas_serial,
        gas_secret,
        gas_type,
        gas_calorific
        )

    def stop_loopenergy(event):
        """Shutdown loopenergy thread on exit."""
        _LOGGER.info("Shutting down loopenergy.")
        controller.terminate()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_loopenergy)

    sensors = [LoopEnergyElec(controller)]

    if gas_serial:
        sensors.append(LoopEnergyGas(controller))

    add_devices(sensors)


# pylint: disable=too-many-instance-attributes
class LoopEnergyDevice(Entity):
    """Implementation of an Loop Energy base sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, controller):
        """Initialize the sensor."""
        self._state = None
        self._unit_of_measurement = 'kW'
        self._controller = controller
        self._name = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def _callback(self):
        self.update_ha_state(True)


# pylint: disable=too-many-instance-attributes
class LoopEnergyElec(LoopEnergyDevice):
    """Implementation of an Loop Energy Electricity sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, controller):
        """Initialize the sensor."""
        super(LoopEnergyElec, self).__init__(controller)
        self._name = 'Power Usage'
        self._controller.subscribe_elecricity(self._callback)

    def update(self):
        """Get the cached Loop energy."""
        self._state = round(self._controller.electricity_useage, 2)


# pylint: disable=too-many-instance-attributes
class LoopEnergyGas(LoopEnergyDevice):
    """Implementation of an Loop Energy Gas sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, controller):
        """Initialize the sensor."""
        super(LoopEnergyGas, self).__init__(controller)
        self._name = 'Gas Usage'
        self._controller.subscribe_gas(self._callback)

    def update(self):
        """Get the cached Loop energy."""
        self._state = round(self._controller.gas_useage, 2)
