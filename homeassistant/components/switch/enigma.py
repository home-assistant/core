"""
homeassistant.components.switch.enigma
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enable or disable standby mode on Enigma2 receivers.

You should have a recent version of OpenWebIf installed.

There is no support for username/password authentication
at this time.

Configuration:

To use the switch you will need to add something like the
following to your config/configuration.yaml

switch:
    platform: enigma
    name: Vu Duo2
    host: 192.168.1.26
    port: 80

Variables:

host
*Required
This is the IP address of your Enigma2 box. Example: 192.168.1.32

port
*Optional
The port your Enigma2 box uses, defaults to 80. Example: 8080

name
*Optional
The name to use when displaying this Enigma2 switch instance.

"""
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_BATTERY_LEVEL, ATTR_ENTITY_PICTURE
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import STATE_ON, STATE_OFF, CONF_HOST
import logging
import requests
import json
from xml.etree import ElementTree

log = logging.getLogger(__name__)
DOMAIN = "enigma"

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return enigma2 boxes. """

    host = config.get(CONF_HOST, None)
    port = config.get('port', "80")
    name = config.get('name', "Enigma2")

    if not host:
        log.error('Missing config variable-host')
        return False

    add_devices_callback([
        EnigmaSwitch(name, host, port)
    ])


class EnigmaSwitch(ToggleEntity):
    """ Provides a switch to toggle standby on an Enigma2 box. """
    def __init__(self, name, host, port):
        self._name = name
        self._host = host
        self._port = port
        self._state = STATE_OFF
        self.state_attr = {ATTR_FRIENDLY_NAME: self._name + ": In Standby"}
        self.update()

    @property
    def should_poll(self):
        """ Need to refresh ourselves. """
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
    def state_attributes(self):
        return self.state_attr

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        #self._state = STATE_ON

        log.info("Turning on Enigma ")
        self.toggle_standby()


    def turn_off(self, **kwargs):
        """ Turn the device off. """
        #self._state = STATE_OFF

        log.info("Turning off Enigma ")
        self.toggle_standby()

    def toggle_standby(self):
        """
        # See http://www.opensat4all.com/forums/tutorials/article/15-dreambox-enigma2-busybox-telnet-commands/
        """
        url = 'http://%s/web/powerstate?newstate=0' % self._host
        log.info('url: %s', url)

        r = requests.get(url)

        try:
            tree = ElementTree.fromstring(r.content)
            result = tree.find('e2instandby').text.strip()
            log.info('e2instandby: %s', result)

            if result == 'true':
                self._state = STATE_OFF
            else:
                self._state = STATE_ON
        except AttributeError as e:
            log.error('There was a problem toggling standby: %s' % e)
            log.error('Entire response: %s' % r.content)
            return

    def update(self):
        """ Update state of the sensor. """
        log.info("updating status enigma")

        url = 'http://%s/api/statusinfo' % self._host
        log.info('url: %s', url)

        r = requests.get(url)

        log.info('response: %s' % r)
        log.info("status_code %s" % r.status_code)

        if r.status_code != 200:
            log.error("There was an error connecting to %s" % url)
            log.error("status_code %s" % r.status_code)
            log.error("error %s" % r.error)

            return

        log.info('r.json: %s' % r.json())

        in_standby = r.json()['inStandby']
        log.info('r.json inStandby: %s' % in_standby)

        if in_standby == 'true':
            self._state = STATE_OFF
            self.state_attr = {ATTR_FRIENDLY_NAME: self._name + ": In Standby"}

        else:
            self._state = STATE_ON
            currservice_name = r.json()['currservice_name']
            currservice_station = r.json()['currservice_station']
            self.state_attr = {ATTR_FRIENDLY_NAME: self._name + ": Active"}


