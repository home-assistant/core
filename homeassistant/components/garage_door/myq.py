"""
Support for Chamberlain garage doors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/garage_door.myq/
"""

import logging
import requests

from homeassistant.components.garage_door import GarageDoorDevice
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_NAME


REQUIREMENTS = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MyQ garage door."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME) if \
        CONF_NAME else "MyQ"  # is this the right way?

    if username is None or password is None:
        logging.getLogger(__name__).error(
            "Missing username or password.")
        return

    myq = MyQAPI(username, password)

    add_devices(MyQGarageDoorDevice(myq, door, name) for door
                in myq.get_garage_doors())


class MyQAPI(object):
    """Class for interacting with the MyQ iOS App API."""

    # as bananas as it seems, this token is valid for all iOS app instances
    APP_ID = \
        "Vj8pQggXLhLy0WHahglCD4N1nAkkXQtGYpq2HrHD7H1nvmbT55KqtN6RSF4ILB%2Fi"
    LOCALE = "en"

    HOST_URI = "myqexternal.myqdevice.com"
    LOGIN_ENDPOINT = "Membership/ValidateUserWithCulture"
    DEVICE_LIST_ENDPOINT = "api/UserDeviceDetails"
    DEVICE_SET_ENDPOINT = "Device/setDeviceAttribute"
    DEVICE_STATUS_ENDPOINT = "/Device/getDeviceAttribute"
    DOOR_STATE = {
        '1': 'open',
        '2': 'close',
        '4': 'opening',
        '5': 'closing',
        '8': 'in_transition',
        '9': 'open'
    }

    def __init__(self, username, password):
        """Initialize the API object."""
        self.username = username
        self.password = password
        self.security_token = None
        self._logged_in = False

    def login(self):
        """Log in to the service."""
        params = {
            'username': self.username,
            'password': self.password,
            'appId': self.APP_ID,
            'culture': 'en'
        }

        login = requests.get(
            'https://{host_uri}/{login_endpoint}'.format(
                host_uri=self.HOST_URI,
                login_endpoint=self.LOGIN_ENDPOINT),
            params=params)
        auth = login.json()
        self.security_token = auth['SecurityToken']
        logging.getLogger(__name__).debug('logged in to MyQ API')
        return True

    def get_devices(self):
        """List all devices."""
        if not self._logged_in:
            self._logged_in = self.login()
        params = {
            'appId': self.APP_ID,
            'securityToken': self.security_token
        }
        devices = requests.get(
            'https://{host_uri}/{device_list_endpoint}'.format(
                host_uri=self.HOST_URI,
                device_list_endpoint=self.DEVICE_LIST_ENDPOINT),
            params=params)
        devices = devices.json()['Devices']
        return devices

    def get_garage_doors(self):
        """List only garage doors."""
        devices = self.get_devices()
        garage_doors = []
        for device in devices:
            if device['MyQDeviceTypeName'] == 'VGDO':
                for attribute in device['Attributes']:
                    if attribute['AttributeDisplayName'] == 'desc' and \
                            attribute['Value'] == 'Garage Door Opener':
                        garage_doors.append(device['DeviceId'])
        return garage_doors

    def get_status(self, device_id):
        """Get device status."""
        params = {
            'appId': self.APP_ID,
            'securityToken': self.security_token,
            'devId': device_id,
            'name': 'doorstate',
        }
        device_status = requests.get(
            'https://{host_uri}/{device_status_endpoint}'.format(
                host_uri=self.HOST_URI,
                device_status_endpoint=self.DEVICE_STATUS_ENDPOINT),
            params=params)
        attval = device_status.json()['AttributeValue']
        garage_state = self.DOOR_STATE[attval]
        return garage_state

    def set_state(self, device_id, state):
        """Set device state."""
        payload = {
            'AttributeName': 'desireddoorstate',
            'DeviceId': device_id,
            'ApplicationId': self.APP_ID,
            'AttributeValue': state,
            'SecurityToken': self.security_token,
        }
        device_action = requests.put(
            'https://{host_uri}/{device_set_endpoint}'.format(
                host_uri=self.HOST_URI,
                device_set_endpoint=self.DEVICE_SET_ENDPOINT),
            data=payload)
        return device_action.status_code == 200


class MyQGarageDoorDevice(GarageDoorDevice):
    """Abstraction of a garage opener device."""

    def __init__(self, myq, device_id, name):
        """Initialize with API object, device id, and name."""
        self.myq = myq
        self.device_id = device_id
        self._name = name

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._name if self._name else "MyQ"

    @property
    def is_closed(self):
        """Return True if door is closed, else False."""
        status = self.myq.get_status(self.device_id)
        return status == 'close'

    def close_door(self):
        """Issue close command to door."""
        self.myq.set_state(self.device_id, '0')
    def open_door(self):
        """Issue open command to door."""
        self.myq.set_state(self.device_id, '1')
