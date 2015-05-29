"""
homeassistant.components.switch.hikvision
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support turning on/off motion detection on Hikvision cameras.

Note: Currently works using default https port only.

CGI API Guide:
http://bit.ly/1RuyUuF

Configuration:

To use the Hikvision motion detection
switch you will need to add something like the
following to your config/configuration.yaml

switch:
    platform: hikvision
    name: Hikvision Cam 1 Motion Detection
    host: 192.168.1.26
    username: YOUR_USERNAME
    password: YOUR_PASSWORD

Variables:

host
*Required
This is the IP address of your Hikvision camera. Example: 192.168.1.32

username
*Required
Your Hikvision camera username

password
*Required
Your Hikvision camera username

name
*Optional
The name to use when displaying this switch instance.

"""
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
import logging
import requests
from requests.auth import HTTPBasicAuth
from xml.etree import ElementTree

_LOGGING = logging.getLogger(__name__)

# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Setup Hikvision Camera config. """

    host = config.get(CONF_HOST, None)
    port = config.get('port', "80")
    name = config.get('name', "Hikvision Camera Motion Detection")
    username = config.get(CONF_USERNAME, "admin")
    password = config.get(CONF_PASSWORD, "12345")
    channel_id = config.get('channel_id', "1")
    xml_namespace = config.get(
        'xml_namespace', "http://www.hikvision.com/ver10/XMLSchema")

    # Required to parse and change xml with the host camera
    _LOGGING.info('ElementTree.register_namespace: %s', xml_namespace)
    ElementTree.register_namespace("", xml_namespace)

    if not host:
        _LOGGING.error('Missing config variable-host')
        return False

    add_devices_callback([
        HikvisionMotionSwitch(
            name, host, port, username, password, channel_id, xml_namespace)
    ])


class HikvisionMotionSwitch(ToggleEntity):

    """ Provides a switch to toggle on/off motion detection. """

    def __init__(self, name, host, port, username,
                 password, channel_id, xml_namespace):
        self._name = name
        self._username = username
        self._password = password
        self._channel_id = channel_id
        self._host = host
        self._port = port
        self._xml_namespace = xml_namespace
        self._state = STATE_OFF
        self.url = 'https://%s/MotionDetection/%s/' % (
            self._host, self._channel_id)
        self.xml_motion_detection_off = None
        self.xml_motion_detection_on = None
        self.update()

    @property
    def should_poll(self):
        """ Poll for status regularly. """
        return True

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device if any. """
        return self._state

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turn the device on. """

        _LOGGING.info("Turning on Motion Detection ")
        self.toggle_motion_detection()

    def turn_off(self, **kwargs):
        """ Turn the device off. """

        _LOGGING.info("Turning off Motion Detection ")
        self.toggle_motion_detection()

    def toggle_motion_detection(self):
        """
        # See http://bit.ly/1KtcW7b
        """

        if self._state == STATE_ON:
            xml = self.xml_motion_detection_off
            self._state = STATE_OFF
        else:
            self._state = STATE_ON
            xml = self.xml_motion_detection_on

        _LOGGING.info('xml:')
        _LOGGING.info("%s", xml)

        response = requests.put(self.url, auth=HTTPBasicAuth(
            self._username, self._password), verify=False, data=xml)
        _LOGGING.info('Response: %s', response.text)

        if response.status_code != 200:
            _LOGGING.error("There was an error connecting to %s", self.url)
            _LOGGING.error("status_code %s", response.esponsestatus_code)
            return

        try:
            tree = ElementTree.fromstring(response.content)
            find_result = tree.findall(
                './/{%s}statusString' % self._xml_namespace)
            if len(find_result) == 0:
                _LOGGING.error("Problem getting motion detection status")
                self.update()
                return

            if find_result[0].text.strip() == 'OK':
                _LOGGING.info('Updated successfully')

        except AttributeError as attib_err:
            _LOGGING.error(
                'There was a problem parsing the response: %s', attib_err)
            self.update()
            return

    def update(self):
        """
        # See http://bit.ly/1KtcW7b
        """
        _LOGGING.info('url: %s', self.url)

        response = requests.get(self.url, auth=HTTPBasicAuth(
            self._username, self._password), verify=False)
        _LOGGING.info('Response: %s', response.text)

        if response.status_code != 200:
            _LOGGING.error("There was an error connecting to %s", self.url)
            _LOGGING.error("status_code %s", response.status_code)
            return

        try:
            tree = ElementTree.fromstring(response.content)
            find_result = tree.findall('.//{%s}enabled' % self._xml_namespace)
            if len(find_result) == 0:
                _LOGGING.error("Problem getting motion detection status")
                return

            result = find_result[0].text.strip()
            _LOGGING.info(
                'Current motion detection state? enabled: %s', result)

            if result == 'true':
                self._state = STATE_ON
                # Save this for future switch off
                find_result[0].text = 'false'
                self.xml_motion_detection_off = ElementTree.tostring(
                    tree, encoding='unicode')
            else:
                self._state = STATE_OFF
                # Save this for future switch on
                find_result[0].text = 'true'
                self.xml_motion_detection_on = ElementTree.tostring(
                    tree, encoding='unicode')

        except AttributeError as attib_err:
            _LOGGING.error(
                'There was a problem parsing '
                'camera motion detection state: %s', attib_err)
            return
