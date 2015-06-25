"""
homeassistant.components.notify.pushbullet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PushBullet platform for notify component.

Configuration:

To use the PushBullet notifier you will need to add something like the
following to your config/configuration.yaml

notify:
  platform: pushbullet
  api_key: YOUR_API_KEY
  device: DEVICE

Variables:

api_key
*Required
Enter the API key for PushBullet. Go to https://www.pushbullet.com/ to retrieve
your API key.
"""
import logging

import time
import json
import requests
import websocket

from threading import Thread
from homeassistant.helpers import validate_config
from homeassistant.components.notify import (DOMAIN, ATTR_TITLE, BaseNotificationService, BaseListenerService)
from homeassistant.const import CONF_API_KEY
from homeassistant import (EventOrigin, EventBus)

from pprint import pprint

_LOGGER = logging.getLogger(__name__)
WEBSOCKET_URL = 'wss://stream.pushbullet.com/websocket/'
ENTITY_ID = "pushbullet.listener"
DEVICE_NAME = "homeassistant"

def get_service(hass, config):
    """ Get the pushbullet notification service. """

    if not validate_config(config,
                           {DOMAIN: [CONF_API_KEY]},
                           _LOGGER):
        return None

    try:
        # pylint: disable=unused-variable
        from pushbullet import PushBullet, InvalidKeyError  # noqa

    except ImportError:
        _LOGGER.exception(
            "Unable to import pushbullet. "
            "Did you maybe not install the 'pushbullet.py' package?")

        return None

    try:
        #register listener
        listener_service = PushBulletListenerService(hass, config[DOMAIN][CONF_API_KEY], DEVICE_NAME, 0, config[DOMAIN][CONF_API_KEY])
        listener_service.run()
        
        return PushBulletNotificationService(config[DOMAIN][CONF_API_KEY])

    except InvalidKeyError:
        _LOGGER.error(
            "Wrong API key supplied. "
            "Get it at https://www.pushbullet.com/account")


class Listener(Thread, websocket.WebSocketApp):
    def __init__(self, api_key, on_push=None):
        """
        :param api_key: pushbullet Key
        :param on_push: function that get's called on all pushes
        """
        self._api_key = api_key

        Thread.__init__(self)
        websocket.WebSocketApp.__init__(self, WEBSOCKET_URL + api_key,
                                        on_open=self.on_open,
                                        on_message=self.on_message,
                                        on_close=self.on_close)

        self.connected = False
        self.last_update = time.time()

        self.on_push = on_push

        # History
        self.history = None
        self.clean_history()

    def clean_history(self):
        self.history = []

    def on_open(self, ws):
        self.connected = True
        self.last_update = time.time()

    def on_close(self, ws):
        _LOGGER.debug('Listener closed')
        self.connected = False

    def on_message(self, ws, message):
        _LOGGER.debug('Message received:' + message)
        try:
            json_message = json.loads(message)
            if json_message["type"] != "nop":
                self.on_push(json_message)
        except Exception as e:
            logging.exception(e)

    def run_forever(self, sockopt=None, sslopt=None, ping_interval=0, ping_timeout=None):
        websocket.WebSocketApp.run_forever(self, sockopt=sockopt, sslopt=sslopt, ping_interval=ping_interval,
                                           ping_timeout=ping_timeout)

    def run(self):
        self.run_forever()


# pylint: disable=too-few-public-methods
class PushBulletNotificationService(BaseNotificationService):
    """ Implements notification service for Pushbullet. """

    def __init__(self, api_key):
        from pushbullet import PushBullet

        self._api_key = api_key
        self.pushbullet = PushBullet(api_key)
        

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        self.pushbullet.push_note(title, message) 
        
        
class PushBulletListenerService(BaseListenerService):
    """ Implements listener service for Pushbullet. """
    
    def __init__(self, hass, api_key, device_name, last_push=0, device_iden=None):
        from pushbullet import PushBullet

        self.hass = hass
        self._api_key = api_key
        self.last_push = last_push
        self.pushbullet = PushBullet(api_key)
        self.listener = Listener(api_key, self.watcher)
        
        self.device = None
        if device_iden:
            results = [d for d in self.pushbullet.devices if d.device_iden == device_iden and d.active]
            self.device = results[0] if results else None

        if not self.device:
            self.device = self.pushbullet.new_device(device_name)            
        
        self.check_pushes()

    def check_pushes(self):
        success, pushes = self.pushbullet.get_pushes(self.last_push)
        if success:
            for push in pushes:
                if ((push.get("target_device_iden", self.device.device_iden) == self.device.device_iden) and not (push.get("dismissed", True))):
                    self.notify(push.get("title", ""), push.get("body", ""))
                    try:
                        self.pushbullet.dismiss_push(push.get("iden"))
                    except:
                        _LOGGER.error("Error while dismissing the message with ID: " + push.get("iden") + ", ")
                self.last_push = max(self.last_push, push.get("created"))    

    def notify(self, title, body):
        self.hass.bus.fire("pushbullet", {'data': title}, EventOrigin.local)
        

    def watcher(self, push):
        if push["type"] == "tickle":
            self.check_pushes()

    def run(self):
        try:                        
            self.listener.start()
        except KeyboardInterrupt:
            self.listener.close()        
        
        