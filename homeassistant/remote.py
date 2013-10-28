"""
homeassistant.remote
~~~~~~~~~~~~~~~~~~~~

A module containing drop in replacements for core parts that will interface
with a remote instance of home assistant.

If a connection error occurs while communicating with the API a
HomeAssistantException will be raised.
"""

import threading
import logging
import json

import requests

import homeassistant as ha
import homeassistant.httpinterface as httpinterface

def _setup_call_api(host, port, base_path, api_password):
    """ Helper method to setup a call api method. """
    port = port or httpinterface.SERVER_PORT

    base_url = "http://{}:{}/api/{}".format(host, port, base_path)

    def _call_api(action, data=None):
        """ Makes a call to the Home Assistant api. """
        data = data or {}

        data['api_password'] = api_password

        return requests.post(base_url + action, data=data)

    return _call_api


class EventBus(ha.EventBus):
    """ Drop-in replacement for a normal eventbus that will forward events to
    a remote eventbus.
    """

    def __init__(self, host, api_password, port=None):
        ha.EventBus.__init__(self)

        self._call_api = _setup_call_api(host, port, "event/", api_password)

        self.logger = logging.getLogger(__name__)

    def fire(self, event_type, event_data=None):
        """ Fire an event. """

        if not event_data:
            event_data = {}

        data = {'event_name': event_type,
                'event_data': json.dumps(event_data)}

        try:
            req = self._call_api("fire", data)

            if req.status_code != 200:
                error = "Error firing event: {} - {}".format(
                            req.status_code, req.text)

                self.logger.error("EventBus:{}".format(error))
                raise ha.HomeAssistantException(error)


        except requests.exceptions.ConnectionError:
            self.logger.exception("EventBus:Error connecting to server")

    def listen(self, event_type, listener):
        """ Not implemented for remote eventbus.

        Will throw NotImplementedError. """
        raise NotImplementedError

    def remove_listener(self, event_type, listener):
        """ Not implemented for remote eventbus.

        Will throw NotImplementedError. """

        raise NotImplementedError

class StateMachine(ha.StateMachine):
    """ Drop-in replacement for a normal statemachine that communicates with a
    remote statemachine.
    """

    def __init__(self, host, api_password, port=None):
        ha.StateMachine.__init__(self, None)

        self._call_api = _setup_call_api(host, port, "state/", api_password)

        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    @property
    def categories(self):
        """ List of categories which states are being tracked. """

        try:
            req = self._call_api("categories")

            return req.json()['categories']

        except requests.exceptions.ConnectionError:
            self.logger.exception("StateMachine:Error connecting to server")
            return []

        except ValueError: # If req.json() can't parse the json
            self.logger.exception("StateMachine:Got unexpected result")
            return []

        except KeyError: # If 'categories' key not in parsed json
            self.logger.exception("StateMachine:Got unexpected result (2)")
            return []

    def set_state(self, category, new_state, attributes=None):
        """ Set the state of a category, add category if it does not exist.

        Attributes is an optional dict to specify attributes of this state. """

        attributes = attributes or {}

        self.lock.acquire()

        data = {'category': category,
                'new_state': new_state,
                'attributes': json.dumps(attributes)}

        try:
            req = self._call_api('change', data)

            if req.status_code != 200:
                error = "Error changing state: {} - {}".format(
                            req.status_code, req.text)

                self.logger.error("StateMachine:{}".format(error))
                raise ha.HomeAssistantException(error)

        except requests.exceptions.ConnectionError:
            self.logger.exception("StateMachine:Error connecting to server")
            raise ha.HomeAssistantException("Error connecting to server")

        finally:
            self.lock.release()

    def get_state(self, category):
        """ Returns a dict (state,last_changed, attributes) describing
            the state of the specified category. """

        try:
            req = self._call_api("get", {'category': category})

            data = req.json()

            return ha.create_state(data['state'],
                            data['attributes'],
                            ha.str_to_datetime(data['last_changed']))

        except requests.exceptions.ConnectionError:
            self.logger.exception("StateMachine:Error connecting to server")
            raise ha.HomeAssistantException("Error connecting to server")

        except ValueError: # If req.json() can't parse the json
            self.logger.exception("StateMachine:Got unexpected result")
            raise ha.HomeAssistantException(
                            "Got unexpected result: {}".format(req.text))

        except KeyError: # If not all expected keys are in the returned JSON
            self.logger.exception("StateMachine:Got unexpected result (2)")
            raise ha.HomeAssistantException(
                            "Got unexpected result (2): {}".format(req.text))
