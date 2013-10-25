"""
homeassistant.test
~~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant modules do what they should do.

"""

import unittest
import time

import requests

import homeassistant as ha
import homeassistant.remote as remote
import homeassistant.httpinterface as httpinterface
import homeassistant.util as util


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
        cls.remote_sm = remote.StateMachine("127.0.0.1", API_PASSWORD)
        cls.remote_eb = remote.EventBus("127.0.0.1", API_PASSWORD)

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


    def test_api_list_state_categories(self):
        """ Test if the debug interface allows us to list state categories. """
        req = requests.post("{}/api/state/categories".format(HTTP_BASE_URL),
                data={"api_password":API_PASSWORD})

        data = req.json()

        self.assertEqual(self.statemachine.categories,
                         data['categories'])


    def test_api_get_state(self):
        """ Test if the debug interface allows us to list state categories. """
        req = requests.post("{}/api/state/get".format(HTTP_BASE_URL),
                data={"api_password":API_PASSWORD,
                      "category": "test"})

        data = req.json()

        state = self.statemachine.get_state("test")
        trunc_last_changed = state.last_changed.replace(microsecond=0)

        self.assertEqual(data['category'], "test")
        self.assertEqual(data['state'], state.state)
        self.assertEqual(util.str_to_datetime(data['last_changed']),
                                                        trunc_last_changed)
        self.assertEqual(data['attributes'], state.attributes)


    def test_api_state_change(self):
        """ Test if we can change the state of a category that exists. """

        self.statemachine.set_state("test", "not_to_be_set_state")

        requests.post("{}/api/state/change".format(HTTP_BASE_URL),
            data={"category":"test",
                  "new_state":"debug_state_change2",
                  "api_password":API_PASSWORD})

        self.assertEqual(self.statemachine.get_state("test").state,
                         "debug_state_change2")


    # pylint: disable=invalid-name
    def test_remote_sm_list_state_categories(self):
        """ Test if the debug interface allows us to list state categories. """

        self.assertEqual(self.statemachine.categories,
                         self.remote_sm.categories)


    def test_remote_sm_get_state(self):
        """ Test if the debug interface allows us to list state categories. """
        remote_state = self.remote_sm.get_state("test")

        state = self.statemachine.get_state("test")
        trunc_last_changed = state.last_changed.replace(microsecond=0)

        self.assertEqual(remote_state.state, state.state)
        self.assertEqual(remote_state.last_changed, trunc_last_changed)
        self.assertEqual(remote_state.attributes, state.attributes)


    def test_remote_sm_state_change(self):
        """ Test if we can change the state of a category that exists. """

        self.remote_sm.set_state("test", "set_remotely", {"test": 1})

        state = self.statemachine.get_state("test")

        self.assertEqual(state.state, "set_remotely")
        self.assertEqual(state.attributes['test'], 1)


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

        self.eventbus.listen_once("test_event_no_data", listener)

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

        self.eventbus.listen_once("test_event_with_data", listener)

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

        self.eventbus.listen_once("test_event_with_data", listener)

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

        self.eventbus.listen_once("test_event_with_bad_data", listener)

        req = requests.post("{}/api/event/fire".format(HTTP_BASE_URL),
            data={"event_name":"test_event_with_bad_data",
                  "event_data":'not json',
                  "api_password":API_PASSWORD})


        # It shouldn't but if it fires, allow the event to take place
        time.sleep(1)

        self.assertEqual(req.status_code, 400)
        self.assertEqual(len(test_value), 0)

    # pylint: disable=invalid-name
    def test_remote_eb_fire_event_with_no_data(self):
        """ Test if the remote eventbus allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.eventbus.listen_once("test_event_no_data", listener)

        self.remote_eb.fire("test_event_no_data")

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    # pylint: disable=invalid-name
    def test_remote_eb_fire_event_with_data(self):
        """ Test if the remote eventbus allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            if event.data["test"] == 1:
                test_value.append(1)

        self.eventbus.listen_once("test_event_with_data", listener)

        self.remote_eb.fire("test_event_with_data", {"test": 1})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

