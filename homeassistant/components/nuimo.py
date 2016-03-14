"""
Component that connects to a Bluetooth reachable Nuimo device.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/nuimo/
"""
from logging import getLogger
import threading
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import validate_config

REQUIREMENTS = [
    'https://github.com/shaftoe/nuimo-raspberrypi-demo/archive/'
    'pip.zip#nuimocore==0.0.1',
    'https://github.com/IanHarvey/bluepy/archive/master.zip#bluepy==1.0.3']

_LOGGER = getLogger(__name__)

DOMAIN = "nuimo"
ENTITY_ID = "{}.nuimo_battery".format(DOMAIN)
EVENT_NUIMO = "nuimo_action"


class NuimoDelegate(object):  # pylint: disable=too-few-public-methods
    """Translate Nuimo bluetooth messages into HASS events."""

    def __init__(self, hass, nuimo):
        """Initialize nuimo delegate object."""
        self._nuimo = nuimo
        self._hass = hass

    # pylint: disable=invalid-name
    def handleNotification(self, c_handle, data):
        """Listen for notifications and send them into bus or states."""
        if int(c_handle) == self._nuimo.characteristicValueHandles['BATTERY']:
            self._hass.states.set(ENTITY_ID, data[0])
        elif int(c_handle) == self._nuimo.characteristicValueHandles['FLY']:
            self._hass.bus.fire(EVENT_NUIMO, {
                'action': 'FLY',
                'value0': data[0],
                'value1': data[1],
            })
        elif int(c_handle) == self._nuimo.characteristicValueHandles['SWIPE']:
            self._hass.bus.fire(EVENT_NUIMO,
                                {'action': 'SWIPE', 'value': data[0]})
        elif int(c_handle) == \
                self._nuimo.characteristicValueHandles['ROTATION']:
            _LOGGER.warning('ROTATION not implemented in Python v3')
        elif int(c_handle) == self._nuimo.characteristicValueHandles['BUTTON']:
            self._hass.bus.fire(EVENT_NUIMO,
                                {'action': 'BUTTON', 'value': data[0]})


class NuimoManager(threading.Thread):
    """Manage Nuimo process."""

    def __init__(self, hass, mac):
        """Initialize Nuimo manager object."""
        super(NuimoManager, self).__init__()
        self._hass = hass
        self._mac = mac
        self._hass_is_running = True
        self._listener = None

        from nuimocore import Nuimo
        self._nuimo = Nuimo(mac)
        self._nuimo.set_delegate(NuimoDelegate(self._hass, self._nuimo))

    def connect(self):
        """Try to connect to Nuimo, return False if connection failed."""
        from nuimocore import BTLEException
        try:
            _LOGGER.info('Trying to connect to Nuimo (MAC %s)...', self._mac)
            self._nuimo.connect()
        except BTLEException:
            _LOGGER.error("""Failed to connect to Nuimo (MAC %s). Make sure to:
1. Disable the Bluetooth device: hciconfig hci0 down
2. Enable the Bluetooth device: hciconfig hci0 up
3. Enable BLE: btmgmt le on
4. Pass the right MAC address: hcitool lescan | grep Nuimo""", self._mac)
            return False
        _LOGGER.info('Nuimo (MAC %s) connected!', self._mac)
        self.display_hass_logo()
        return True

    def _reconnect(self, retries=5):
        """Try a `retries` number of reconnects."""
        for retry in range(1, retries+1):
            _LOGGER.warning('Connection with Nuimo (MAC %s) lost, '
                            'reconnection attempt %s of %s',
                            self._mac,
                            retry,
                            retries)
            success = self.connect()
            if success:
                return True
        return False

    def run(self):
        """Start the thread."""
        from nuimocore import BTLEException
        self._listener = self._hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                                    self.stop)
        while self._hass_is_running:
            try:
                self._nuimo.waitForNotifications()
            except BTLEException as btle_exception:
                # Try to reconnect when disconnection exception is
                # thrown. Ignore any other Bluetooth exception for now
                if btle_exception.code == BTLEException.DISCONNECTED:
                    if not self._reconnect():
                        self.stop(None)
            except ValueError:
                # This caches an open bug with nuimocore and Python v3
                # when KeyboardException is risen
                # https://github.com/getsenic/nuimo-raspberrypi-demo/issues/8
                pass

    def stop(self, event):  # pylint: disable=unused-argument
        """Set _hass_is_running as false, stopping the Nuimo polling."""
        _LOGGER.info('Stopping Nuimo (MAC %s) background process', self._mac)
        self._hass_is_running = False
        self._hass.bus.remove_listener(EVENT_HOMEASSISTANT_STOP,
                                       self._listener)

    def display_hass_logo(self):
        """Display HASS logo on Nuimo for 4 seconds."""
        self._nuimo.displayLedMatrix(
            "    *    " +
            "   * * * " +
            "  *   ** " +
            " *     * " +
            "*********" +
            " *     * " +
            " *     * " +
            " *     * " +
            " ******* ", 4.0)


def setup(hass, config):
    """Setup the Nuimo component."""
    if not validate_config(config, {DOMAIN: ['mac']}, _LOGGER):
        _LOGGER.error("You must define the MAC address "
                      "for your Nuimo in the config file. "
                      "Setup aborted")
        return False
    mac = config.get(DOMAIN)['mac']

    # Setup nuimo
    manager = NuimoManager(hass, mac)
    # NOTE: connect() will block the main thread for a few seconds
    # if Nuimo device is not available
    success = manager.connect()
    if not success:
        return False
    manager.start()
    return True
