"""
homeassistant.test
~~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant modules do what they should do.

"""

import unittest
import time

import requests

from . import EventBus, StateMachine, Event, EVENT_START, EVENT_SHUTDOWN
from .httpinterface import HTTPInterface, SERVER_PORT


API_PASSWORD = "test1234"

HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)


class HomeAssistantTestCase(unittest.TestCase):
    """ Base class for Home Assistant test cases. """

    @classmethod
    def setUpClass(cls):
        cls.eventbus = EventBus()
        cls.statemachine = StateMachine(cls.eventbus)
        cls.init_ha = False

        def start_ha(self):
            """ Classes will have to call this from setUp()
                after initializing their components. """
            cls.eventbus.fire(Event(EVENT_START))

            # Give objects time to startup
            time.sleep(1)

        cls.start_ha = start_ha

    @classmethod
    def tearDownClass(cls):
        cls.eventbus.fire(Event(EVENT_SHUTDOWN))

        time.sleep(1)


class TestHTTPInterface(HomeAssistantTestCase):
    """ Test the HTTP debug interface and API. """

    HTTP_init = False

    def setUp(self):
        """ Initialize the HTTP interface if not started yet. """
        if not TestHTTPInterface.HTTP_init:
            TestHTTPInterface.HTTP_init = True

            HTTPInterface(self.eventbus, self.statemachine, API_PASSWORD)

            self.statemachine.set_state("test", "INIT_STATE")

            self.start_ha()


    def test_debug_interface(self):
        """ Test if we can login by comparing not logged in screen to logged in screen. """
        self.assertNotEqual(requests.get(HTTP_BASE_URL).text,
                            requests.get("{}/?api_password={}".format(HTTP_BASE_URL, API_PASSWORD)).text)


    def test_debug_state_change(self):
        """ Test if the debug interface allows us to change a state. """
        requests.post("{}/state/change".format(HTTP_BASE_URL), data={"category":"test",
                                                                "new_state":"debug_state_change",
                                                                "api_password":API_PASSWORD})

        self.assertEqual(self.statemachine.get_state("test").state, "debug_state_change")


    def test_api_password(self):
        """ Test if we get access denied if we omit or provide a wrong api password. """
        req = requests.post("{}/api/state/change".format(HTTP_BASE_URL))

        self.assertEqual(req.status_code, 401)

        req = requests.post("{}/api/state/change".format(HTTP_BASE_URL, data={"api_password":"not the password"}))

        self.assertEqual(req.status_code, 401)


    def test_api_state_change(self):
        """ Test if the API allows us to change a state. """
        requests.post("{}/api/state/change".format(HTTP_BASE_URL), data={"category":"test",
                                                                    "new_state":"debug_state_change2",
                                                                    "api_password":API_PASSWORD})

        self.assertEqual(self.statemachine.get_state("test").state, "debug_state_change2")

    def test_api_state_change_of_non_existing_category(self):
        """ Test if the API allows us to change a state of a non existing category. """
        req = requests.post("{}/api/state/change".format(HTTP_BASE_URL), data={"category":"test_category_that_does_not_exist",
                                                                    "new_state":"debug_state_change",
                                                                    "api_password":API_PASSWORD})

        self.assertEqual(req.status_code, 200)
        self.assertEqual(self.statemachine.get_state("test_category_that_does_not_exist").state, "debug_state_change")

    def test_api_fire_event_with_no_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.eventbus.listen("test_event_no_data", listener)

        requests.post("{}/api/event/fire".format(HTTP_BASE_URL), data={"event_name":"test_event_no_data",
                                                                  "event_data":"",
                                                                  "api_password":API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)


    def test_api_fire_event_with_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):
            """ Helper method that will verify that our event got called and
                that test if our data came through. """
            if "test" in event.data:
                test_value.append(1)

        self.eventbus.listen("test_event_with_data", listener)

        requests.post("{}/api/event/fire".format(HTTP_BASE_URL), data={"event_name":"test_event_with_data",
                                                                  "event_data":'{"test": 1}',
                                                                  "api_password":API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)


    def test_api_fire_event_with_invalid_json(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.eventbus.listen("test_event_with_bad_data", listener)

        req = requests.post("{}/api/event/fire".format(HTTP_BASE_URL), data={"event_name":"test_event_with_bad_data",
                                                                        "event_data":'not json',
                                                                        "api_password":API_PASSWORD})


        # It shouldn't but if it fires, allow the event to take place
        time.sleep(1)

        self.assertEqual(req.status_code, 400)
        self.assertEqual(len(test_value), 0)
