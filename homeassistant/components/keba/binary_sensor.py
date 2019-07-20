"""Support for KEBA charging station binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """Set up the KEBA charging station platform."""
    _LOGGER.debug("Initializing KEBA charging station binary sensors")
    keba = hass.data[DOMAIN]

    sensors = [
        KebaBinarySensor('Online', keba, 'Wallbox', 'connectifity'),
        KebaBinarySensor('Plug', keba, 'Plug', 'plug'),
        KebaBinarySensor('State', keba, 'Charging state', 'power'),
        KebaBinarySensor('Tmo FS', keba, 'Failsafe Mode', 'safety')
    ]
    async_add_entities(sensors)


class KebaBinarySensor(BinarySensorDevice):
    """Representation of a binary sensor of a KEBA charging station."""

    def __init__(self, key, keba, sensor_name, device_class):
        """Initialize the KEBA Sensor."""
        self._key = key
        self._keba = keba
        self._name = sensor_name
        self._device_class = device_class
        self._is_on = None
        self._attributes = {}

    @property
    def should_poll(self):
        """Data updated by KebaHandler."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return self._keba.device_name + self._name

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._is_on

    @property
    def device_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        return self._attributes.items()

    async def async_update(self):
        """Get latest cached states from the device."""
        if self._key == 'Online':
            self._is_on = self._keba.get_value(self._key)
            self._attributes['Product'] = self._keba.get_value('Product')
            self._attributes['Serial'] = self._keba.get_value('Serial')
            self._attributes['Firmware'] = self._keba.get_value('Firmware')

            secs = self._keba.get_value('Sec')

            text = ""
            if secs is not None:
                if secs < 60:
                    text = str(int(secs)) + " secs"
                elif secs < 3600:
                    text = str(int(secs / 60)) + " mins"
                elif secs < 86400:
                    text = str(int(secs / 3600)) + " hours"
                elif secs < 31536000:
                    text = str(int(secs / 86400)) + " days"
                else:
                    text = str(int(secs / 31536000)) + " years, " + \
                           str(int((secs % 31536000) / 86400)) + " days"
                self._attributes['Device uptime'] = text

        elif self._key == 'Plug':
            plug_state = self._keba.get_value(self._key)
            if plug_state is not None:
                self._is_on = plug_state > 3
                self._attributes["Plugged on wallbox"] = plug_state > 0
                self._attributes["Plug locked"] = \
                    plug_state == 3 | plug_state == 7
                self._attributes["Plugged on EV"] = plug_state > 4

        elif self._key == 'State':
            plug_state = self._keba.get_value(self._key)
            if plug_state is not None:
                switcher = {
                    0: "starting",
                    1: "not ready for charging",
                    2: "ready for charging",
                    3: "charging",
                    4: "error",
                    5: "authorization rejected"
                }
                self._is_on = plug_state == 3
                self._attributes['status'] = switcher.get(
                    plug_state, "State undefined")
                self._attributes['max charging rate'] = \
                    str(self._keba.get_value("Max curr")) + " A"

        elif self._key == 'Tmo FS':
            plug_state = self._keba.get_value(self._key)
            if plug_state is not None:
                self._is_on = plug_state == 0
                self._attributes['Timeout'] = \
                    str(self._keba.get_value("Tmo FS")) + " s"
                self._attributes['Current in case of failure'] = \
                    str(self._keba.get_value("Curr FS")) + " A"
        elif self._key == 'Authreq':
            self._is_on = self._keba.get_value(self._key) == 0

    def update_callback(self):
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._keba.add_update_listener(self.update_callback)
