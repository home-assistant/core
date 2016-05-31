"""

Support for Raspberry Pi garage door opener.

Developed by Johann 'KellerZA' Kellerman

https://github.com/andrewshilliday/garage-door-controller

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/garage_door.raspberry/

"""

import logging
from homeassistant.components.garage_door import GarageDoorDevice

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['requests']

# Get returns
# {"timestamp": 1464627981, "update": [["left", "open", 1464627945.459889]]}
GD_GET = '{}/upd'
# Set using: ?id=left
GD_SET = '{}/clk'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink garage door platform."""
    import requests

    url = config.get('url', 'http://127.0.0.1:8080')

    req = requests.get(GD_GET.format(url))
    if req.status_code == 200:
        res = req.json()
        # _LOGGER.info(str(res))
        update = res['update']
        add_devices([RaspberryGarageDoor(url, door[0]) for door in update])


class RaspberryGarageDoor(GarageDoorDevice):
    """Representation of a Raspberry garage door."""

    def __init__(self, url, name):
        """Initialize the garage door."""
        self._url = url
        self._name = name
        self._state = ''

    @property
    def unique_id(self):
        """Return the ID of this wink garage door."""
        return "{}.{}".format(self.__class__, self._name)

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._name

    def update(self):
        """Update the state of the garage door."""
        import requests
        req = requests.get(GD_GET.format(self._url))
        if req.status_code == 200:
            res = req.json()
            upd = res['update']
            thedoor = [door[1] for door in upd if door[0] == self._name]
            if thedoor:
                self._state = thedoor[0]

    @property
    def is_closed(self):
        """Return true if door is closed."""
        return self._state == 'closed'

    @property
    def available(self):
        """True if connection == True."""
        return True

    def _click(self):
        import requests
        # _LOGGER.info('Clicking '+str(self._name))
        requests.get(GD_SET.format(self._url), {'id': self._name})

    def close_door(self):
        """Close the door."""
        if not self.is_closed:
            self._click()

    def open_door(self):
        """Open the door."""
        # _LOGGER.info('state='+str(self._state))
        if self.is_closed:
            self._click()
            
