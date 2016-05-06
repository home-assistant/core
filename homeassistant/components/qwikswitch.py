"""
Support for Qwikswitch lights and switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/qwikswitch
"""

import logging

REQUIREMENTS = ['https://github.com/kellerza/pyqwikswitch/archive/v0.1.zip'
                '#pyqwikswitch==0.1']
DEPENDENCIES = []

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'qwikswitch'
DISCOVER_LIGHTS = 'qwikswitch.light'
DISCOVER_SWITCHES = 'qwikswitch.switch'

ADD_DEVICES = None


class QSToggleEntity(object):
    # pylint: disable=line-too-long
    """Representation of a Qwikswitch Entiry.

    Implement base QS methods. Modeled around HA ToggleEntity[1] & should only
    be used in a class that extends both QSToggleEntity *and* ToggleEntity.

    Implemented:
     - QSLight extends QSToggleEntity and Light[2] (ToggleEntity[1])
     - QSSwitch extends QSToggleEntity and SwitchDevice[3] (ToggleEntity[1])

    [1] https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/helpers/entity.py  # NOQA
    [2] https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/light/__init__.py  # NOQA
    [3] https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/switch/__init__.py  # NOQA
    """

    def __init__(self, qsitem, qsusb):
        """Initialize the light."""
        self._id = qsitem['id']
        self._name = qsitem['name']
        self._qsusb = qsusb
        self._value = qsitem.get('value', 0)
        self._dim = qsitem['type'] == 'dim'

    @property
    def brightness(self):
        """Return the brightness of this light between 0..100."""
        return self._value if self._dim else None

    # pylint: disable=no-self-use
    @property
    def should_poll(self):
        """State Polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def is_on(self):
        """Check if On (non-zero)."""
        return self._value > 0

    def update_value(self, value):
        """Decode QSUSB value & update HA state."""
        self._value = value
        # pylint: disable=no-member
        super().update_ha_state()  # Part of Entity/ToggleEntity
        return self._value

    # pylint: disable=unused-argument
    def turn_on(self, **kwargs):
        """Turn the device on."""
        from homeassistant.components.light import ATTR_BRIGHTNESS
        if ATTR_BRIGHTNESS in kwargs:
            self._value = kwargs[ATTR_BRIGHTNESS]
        else:
            self._value = 100
        return self._qsusb.set(self._id, self._value)

    # pylint: disable=unused-argument
    def turn_off(self, **kwargs):
        """Turn the device off."""
        return self._qsusb.set(self._id, 0)


# pylint: disable=too-many-locals
def setup(hass, config):
    """Setup the QSUSB component."""
    from pyqwikswitch import QSUsb
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP
    from homeassistant.components.light import Light
    from homeassistant.components.switch import SwitchDevice
    from homeassistant.components.discovery import discover

    try:
        url = config[DOMAIN].get('url', 'http://127.0.0.1:2020')
        qsusb = QSUsb(url, _LOGGER)

        # Ensure qsusb terminates threads correctly
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             lambda event: qsusb.stop())
    except ValueError as val_err:
        _LOGGER.error(str(val_err))
        return False

    global ADD_DEVICES  # pylint: disable=global-statement
    ADD_DEVICES = {}
    qs_devices = {}

    # Register add_device callbacks onto the gloabl ADD_DEVICES
    for comp_name in ('switch', 'light'):
        discover(hass, 'qwikswitch.'+comp_name, component=comp_name)
        # discover method seems to wrap these commands -- simplify
        # bootstrap.setup_component(hass, component.DOMAIN, config)
        # hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
        #              {ATTR_SERVICE: '{}.qwikswitch'.format(comp_name),
        #               ATTR_DISCOVERED: {}})

    def add_device(platform, qs_id, device):
        """Add a new QS device, using add_devices from the platforms.

        Platforms will store add_devices in ADD_DEVICES
        """
        if platform in ADD_DEVICES:
            ADD_DEVICES[platform]([device])
        else:
            _LOGGER.error('Platform %s/qwikswitch was not discovered',
                          platform)
        qs_devices[qs_id] = device

    class QSLight(QSToggleEntity, Light):
        """Light based on a Qwikswitch relay/dimmer module."""

    class QSSwitch(QSToggleEntity, SwitchDevice):
        """Switch based on a Qwikswitch relay module."""

    def qs_callback(item):
        """Typically a btn press or update signal."""
        from pyqwikswitch import CMD_BUTTONS

        if item.get('type', '') in CMD_BUTTONS:
            # Button press, fire a hass event
            _LOGGER.info('qwikswitch.button.%s', item['id'])
            hass.bus.fire('qwikswitch.button.{}'.format(item['id']))
            return

        # Perform a normal update of all devices
        qsreply = qsusb.devices()
        if qsreply is False:
            return
        for item in qsreply:
            item_id = item.get('id', '')

            # Add this device if it is not known
            if item_id not in qs_devices:
                _LOGGER.info('Add QS device %s', item['name'])
                if item['type'] == 'dim':
                    add_device('light', item_id, QSLight(item, qsusb))
                elif item['type'] == 'rel':
                    if item['name'].lower().endswith(' switch'):
                        # Remove the ' Switch' name postfix for HA
                        item['name'] = item['name'][:-7]
                        add_device('switch', item_id, QSSwitch(item, qsusb))
                    else:
                        add_device('light', item_id, QSLight(item, qsusb))
                else:
                    qs_devices[item_id] = None
                    _LOGGER.error('QwikSwitch: type=%s not supported',
                                  item['type'])

            if qs_devices.get(item_id, '') is not None:
                qs_devices[item_id].update_value(item['value'])

    qsusb.listen(callback=qs_callback, timeout=10)
    return True
