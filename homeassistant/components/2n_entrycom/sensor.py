'''Compoenent for handling 2n Entrycom'''

import sys
import asyncio
import async_timeout
import aiohttp
import logging
import voluptuous as vol
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA

from homeassistant.const import (
            CONF_ENTITY_ID,
            CONF_FRIENDLY_NAME,
            EVENT_HOMEASSISTANT_STOP,
            STATE_UNKNOWN)

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import generate_entity_id

import json

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = '2n keycard_validator'
CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'
CONF_URL = 'entrycom_url'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_URL): cv.string,
})

async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the sensor platform."""
    uname = config.get(CONF_USERNAME)
    passw = config.get(CONF_PASSWORD)
    _LOGGER.info('2n setting up')
    friendly_name = 'Doorbell'
    base_url = '{}api/'.format(config.get(CONF_URL))

    sensor = TwoNSensor(uname, 
        passw, 
        friendly_name, 
        base_url, 
        hass, 
        )
    hass.bus.async_listen_once(
                  EVENT_HOMEASSISTANT_STOP,
                  sensor.async_stop_2n_sensor())
    
    async_add_devices([sensor], True)



class TwoNSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, username, password, friendly_name, url, hass):
        """Initialize the sensor."""
        _LOGGER.info("initializing 2n_sensor")
        self._entity_id = 'sensor.haustuer' 
        self._name = friendly_name
        self._uname = username
        self._passw = password
        self._base_url = url
        self._device_class = '2n_sensor'
        self._hass = hass
        self._id = None
        self._state = None
        self._2n_loop_task = None
        self._subscribe_url = "{}log/subscribe?filter=KeyPressed,CardEntered".format(
                self._base_url)
        self._event_url = 'bla'        
        _LOGGER.info('2n setup done')


    @asyncio.coroutine
    def async_added_to_hass(self):
        _LOGGER.info('starting loop for the state of the door')
        self._2n_loop_task = self._hass.loop.create_task(
                self.async_get_2n_state())

    @asyncio.coroutine
    def async_stop_2n_sensor(self):
        if self._2n_loop_task:
            self._2n_loop_task.cancel()

    #@asyncio.coroutine
    async def async_get_2n_state(self):
        while True:
            websession = async_get_clientsession(self._hass)
            _LOGGER.info('2n getting id')
            self._id = None
            try:
                _LOGGER.info('2n getting id2')
                with async_timeout.timeout(10, loop=self._hass.loop):
                    response = await websession.get(
                                    self._subscribe_url,
                                    auth=aiohttp.BasicAuth(self._uname, self._passw),
                                    verify_ssl=False) # don't want to stop working
                                                      # when there is no cert on the 2n

                    if(response.status == 200):
                        text = await response.text()
                        jData = json.loads(text)
                        self._id = jData["result"]["id"]
                        _LOGGER.info("2n entrycom: attaching to id: {}".format(self._id))
                        self._event_url = "{}log/pull?id={}&timeout=600".format(self._base_url, self._id)
                        
            except:
                _LOGGER.info("exception when setting up subscription: {}".format(sys.exc_info()[0]))
            
            if self._id is None:
                _LOGGER.error("error subscribing to 2n! retrying in 5min!")
                await asyncio.sleep(300)
                continue
                
            while True:
                resp = None
                try:
                    with async_timeout.timeout(310, loop=self._hass.loop):
                        resp = await websession.get(
                                self._event_url,
                                auth=aiohttp.BasicAuth(self._uname, self._passw),
                                verify_ssl=False)
              
                        text = await resp.text()
                        
                        if(resp.status == 200):
                            jData = json.loads(text)
                            if ('success' in jData and 
                                    jData['success'] and 
                                    'result' in jData and len(jData['result']['events']) > 0):
                                if jData['result']['events'][0]['event'] == 'CardEntered':
                                    if jData['result']['events'][0]['params']['valid']:
                                        self._state = 'ValidCardEntered'
                                    else:
                                        self._state = 'InvalidCardEvent: {}'.format(
                                                jData['result']['events'][0]['params']['uid'])
                                elif jData['result']['events'][0]['event'] == 'KeyPressed':
                                    self._state = 'KeyPress: {}'.format(
                                                jData['result']['events'][0]['params']['key'])
                                elif jData['result']['events'][0]['event'] == 'MotionDetected':
                                    if jData['result']['events'][0]['params']['state'] == 'in':
                                        self._state = 'StartOfMotion'
                                    else:
                                        self._state = 'EndOfMotion'
                                elif jData['result']['events'][0]['event'] == 'NoiseDetected':
                                    if jData['result']['events'][0]['params']['state'] == 'in':
                                        self._state = 'StartOfNoise'
                                    else:
                                        self._state = 'EndOfNoise'
                                _LOGGER.info('Set event on 2n: {}'.format(self._state))
                            else:
                                self._state = False
                            self.async_schedule_update_ha_state()
                            if self._state == 'ValidCardEntered' or self._state[:9] == 'KeyPress:':
                                await asyncio.sleep(5)
                                self._state = None
                                self.async_schedule_update_ha_state()

                except:
                    _LOGGER.info(
                        'exception when trying to poll data')
                    _LOGGER.info("exception: {}".format(sys.exc_info()[0]))

                if resp is None or resp.status != 200:
                    self._state = False
                    self.async_schedule_update_ha_state()
                    _LOGGER.info('unsubscribing from stream to reinitialize')
                    unsubscribe_url = "{}log/unsubscribe?id={}".format(
                            self._base_url, self._id)

                    try:
                        with async_timeout.timeout(10, loop=self._hass.loop):
                            resp = await websession.get(
                                    self._event_url,
                                    auth=aiohttp.BasicAuth(self._uname, self._passw),
                                    verify_ssl=False)
                    except:
                        _LOGGER.info('exception while trying to end subscription')
                        _LOGGER.info("exception: {}".format(sys.exc_info()[0]))
                    break


    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        _LOGGER.info("called 2n should_poll") 
        return False

    @property
    def entity_id(self):
        return self._entity_id


