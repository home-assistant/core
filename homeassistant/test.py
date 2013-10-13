"""
homeassistant.test
~~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant modules do what they should do.

"""

import unittest
import time

import requests

import homeassistant as ha
import homeassistant.httpinterface as httpinterface


API_PASSWORD = "test1234"

HTTP_BASE_URL = "http://127.0.0.1:{}".format(httpinterface.SERVER_PORT)

# pylint: disable=too-many-public-methods
class TestHTTPInterface(unittest.TestCase):
    """ Test the HTTP debug interface and API. """

    HTTP_init = False

    def setUp(self):    # pylint: disable=invalid-name
        """ Initialize the HTTP interface if not started yet. """
        if not TestHTTPInterface.HTTP_init:
            TestHTTPInterface.HTTP_init = True

            httpinterface.HTTPInterface(self.eventbus, self.statemachine,
                                                                API_PASSWORD)

            self.statemachine.set_state("test", "INIT_STATE")

            self.eventbus.fire(ha.EVENT_START)

            # Give objects time to startup
            time.sleep(1)

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.eventbus = ha.EventBus()
        cls.statemachine = ha.StateMachine(cls.eventbus)

    def test_debug_interface(self):
        """ Test if we can login by comparing not logged in screen to
            logged in screen. """
        self.assertNotEqual(requests.get(HTTP_BASE_URL).text,
                            requests.get("{}/?api_password={}".format(
                                HTTP_BASE_URL, API_PASSWORD)).text)


    def test_debug_state_change(self):
        """ Test if the debug interface allows us to change a state. """
        requests.post("{}/state/change".format(HTTP_BASE_URL),
            data={"category":"test",
                  "new_state":"debug_state_change",
                  "api_password":API_PASSWORD})

        self.assertEqual(self.statemachine.get_state("test").state,
                         "debug_state_change")


    def test_api_password(self):
        """ Test if we get access denied if we omit or provide
            a wrong api password. """
        req = requests.post("{}/api/state/change".format(HTTP_BASE_URL))

        self.assertEqual(req.status_code, 401)

        req = requests.post("{}/api/state/change".format(HTTP_BASE_URL,
                data={"api_password":"not the password"}))

        self.assertEqual(req.status_code, 401)


    def test_api_state_change(self):
        """ Test if we can change the state of a category that exists. """

        self.statemachine.set_state("test", "not_to_be_set_state")

        requests.post("{}/api/state/change".format(HTTP_BASE_URL),
            data={"category":"test",
                  "new_state":"debug_state_change2",
                  "api_password":API_PASSWORD})

        self.assertEqual(self.statemachine.get_state("test").state,
                         "debug_state_change2")

    def test_api_multiple_state_change(self):
        """ Test if we can change multiple states in 1 request. """

        self.statemachine.set_state("test", "not_to_be_set_state")
        self.statemachine.set_state("test2", "not_to_be_set_state")

        requests.post("{}/api/state/change".format(HTTP_BASE_URL),
            data={"category": ["test", "test2"],
                  "new_state": ["test_state_1", "test_state_2"],
                  "api_password":API_PASSWORD})

        self.assertEqual(self.statemachine.get_state("test").state,
                         "test_state_1")
        self.assertEqual(self.statemachine.get_state("test2").state,
                         "test_state_2")

    # pylint: disable=invalid-name
    def test_api_state_change_of_non_existing_category(self):
        """ Test if the API allows us to change a state of
            a non existing category. """

        new_state = "debug_state_change"

        req = requests.post("{}/api/state/change".format(HTTP_BASE_URL),
                data={"category":"test_category_that_does_not_exist",
                      "new_state":new_state,
                      "api_password":API_PASSWORD})

        cur_state = (self.statemachine.
                        get_state("test_category_that_does_not_exist").state)

        self.assertEqual(req.status_code, 200)
        self.assertEqual(cur_state, new_state)

    # pylint: disable=invalid-name
    def test_api_fire_event_with_no_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.eventbus.listen("test_event_no_data", listener)

        requests.post("{}/api/event/fire".format(HTTP_BASE_URL),
            data={"event_name":"test_event_no_data",
                  "event_data":"",
                  "api_password":API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)


    # pylint: disable=invalid-name
    def test_api_fire_event_with_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify that our event got called and
                that test if our data came through. """
            if "test" in event.data:
                test_value.append(1)

        self.eventbus.listen("test_event_with_data", listener)

        requests.post("{}/api/event/fire".format(HTTP_BASE_URL),
            data={"event_name":"test_event_with_data",
                  "event_data":'{"test": 1}',
                  "api_password":API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)


    # pylint: disable=invalid-name
    def test_api_fire_event_with_no_params(self):
        """ Test how the API respsonds when we specify no event attributes. """
        test_value = []

        def listener(event):
            """ Helper method that will verify that our event got called and
                that test if our data came through. """
            if "test" in event.data:
                test_value.append(1)

        self.eventbus.listen("test_event_with_data", listener)

        requests.post("{}/api/event/fire".format(HTTP_BASE_URL),
            data={"api_password":API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 0)


    # pylint: disable=invalid-name
    def test_api_fire_event_with_invalid_json(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):    # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.eventbus.listen("test_event_with_bad_data", listener)

        req = requests.post("{}/api/event/fire".format(HTTP_BASE_URL),
            data={"event_name":"test_event_with_bad_data",
                  "event_data":'not json',
                  "api_password":API_PASSWORD})


        # It shouldn't but if it fires, allow the event to take place
        time.sleep(1)

        self.assertEqual(req.status_code, 400)
        self.assertEqual(len(test_value), 0)
