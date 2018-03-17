"""The tests for the pilight component."""
import logging
import unittest
from unittest.mock import patch
import socket
from datetime import timedelta

import pytest

from homeassistant import core as ha
from homeassistant.setup import setup_component
from homeassistant.components import pilight
from homeassistant.util import dt as dt_util

from tests.common import get_test_home_assistant, assert_setup_component

_LOGGER = logging.getLogger(__name__)


class PilightDaemonSim:
    """Class to fake the interface of the pilight python package.

    Is used in an asyncio loop, thus the mock cannot be accessed to
    determine if methods where called?!
    This is solved here in a hackish way by printing errors
    that can be checked using logging.error mocks.
    """

    callback = None
    called = None

    test_message = {"protocol": "kaku_switch",
                    "uuid": "1-2-3-4",
                    "message": {
                        "id": 0,
                        "unit": 0,
                        "off": 1}}

    def __init__(self, host, port):
        """Init pilight client, ignore parameters."""
        pass

    def send_code(self, call):  # pylint: disable=no-self-use
        """Called pilight.send service is called."""
        _LOGGER.error('PilightDaemonSim payload: ' + str(call))

    def start(self):
        """Called homeassistant.start is called.

        Also sends one test message after start up
        """
        _LOGGER.error('PilightDaemonSim start')
        # Fake one code receive after daemon started
        if not self.called:
            self.callback(self.test_message)
            self.called = True

    def stop(self):  # pylint: disable=no-self-use
        """Called homeassistant.stop is called."""
        _LOGGER.error('PilightDaemonSim stop')

    def set_callback(self, function):
        """Callback called  on event pilight.pilight_received."""
        self.callback = function
        _LOGGER.error('PilightDaemonSim callback: ' + str(function))


@pytest.mark.skip("Flaky")
class TestPilight(unittest.TestCase):
    """Test the Pilight component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.skip_teardown_stop = False

    def tearDown(self):
        """Stop everything that was started."""
        if not self.skip_teardown_stop:
            self.hass.stop()

    @patch('homeassistant.components.pilight._LOGGER.error')
    def test_connection_failed_error(self, mock_error):
        """Try to connect at 127.0.0.1:5000 with socket error."""
        with assert_setup_component(4):
            with patch('pilight.pilight.Client',
                       side_effect=socket.error) as mock_client:
                self.assertFalse(setup_component(
                    self.hass, pilight.DOMAIN, {pilight.DOMAIN: {}}))
                mock_client.assert_called_once_with(host=pilight.DEFAULT_HOST,
                                                    port=pilight.DEFAULT_PORT)
                self.assertEqual(1, mock_error.call_count)

    @patch('homeassistant.components.pilight._LOGGER.error')
    def test_connection_timeout_error(self, mock_error):
        """Try to connect at 127.0.0.1:5000 with socket timeout."""
        with assert_setup_component(4):
            with patch('pilight.pilight.Client',
                       side_effect=socket.timeout) as mock_client:
                self.assertFalse(setup_component(
                    self.hass, pilight.DOMAIN, {pilight.DOMAIN: {}}))
                mock_client.assert_called_once_with(host=pilight.DEFAULT_HOST,
                                                    port=pilight.DEFAULT_PORT)
                self.assertEqual(1, mock_error.call_count)

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('homeassistant.core._LOGGER.error')
    @patch('tests.components.test_pilight._LOGGER.error')
    def test_send_code_no_protocol(self, mock_pilight_error, mock_error):
        """Try to send data without protocol information, should give error."""
        with assert_setup_component(4):
            self.assertTrue(setup_component(
                self.hass, pilight.DOMAIN, {pilight.DOMAIN: {}}))

            # Call without protocol info, should be ignored with error
            self.hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                    service_data={'noprotocol': 'test',
                                                  'value': 42},
                                    blocking=True)
            self.hass.block_till_done()
            error_log_call = mock_error.call_args_list[-1]
            self.assertTrue(
                'required key not provided @ data[\'protocol\']' in
                str(error_log_call))

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('tests.components.test_pilight._LOGGER.error')
    def test_send_code(self, mock_pilight_error):
        """Try to send proper data."""
        with assert_setup_component(4):
            self.assertTrue(setup_component(
                self.hass, pilight.DOMAIN, {pilight.DOMAIN: {}}))

            # Call with protocol info, should not give error
            service_data = {'protocol': 'test',
                            'value': 42}
            self.hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                    service_data=service_data,
                                    blocking=True)
            self.hass.block_till_done()
            error_log_call = mock_pilight_error.call_args_list[-1]
            service_data['protocol'] = [service_data['protocol']]
            self.assertTrue(str(service_data) in str(error_log_call))

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('homeassistant.components.pilight._LOGGER.error')
    def test_send_code_fail(self, mock_pilight_error):
        """Check IOError exception error message."""
        with assert_setup_component(4):
            with patch('pilight.pilight.Client.send_code',
                       side_effect=IOError):
                self.assertTrue(setup_component(
                    self.hass, pilight.DOMAIN, {pilight.DOMAIN: {}}))

                # Call with protocol info, should not give error
                service_data = {'protocol': 'test',
                                'value': 42}
                self.hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                        service_data=service_data,
                                        blocking=True)
                self.hass.block_till_done()
                error_log_call = mock_pilight_error.call_args_list[-1]
                self.assertTrue('Pilight send failed' in str(error_log_call))

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('tests.components.test_pilight._LOGGER.error')
    def test_send_code_delay(self, mock_pilight_error):
        """Try to send proper data with delay afterwards."""
        with assert_setup_component(4):
            self.assertTrue(setup_component(
                self.hass, pilight.DOMAIN,
                {pilight.DOMAIN: {pilight.CONF_SEND_DELAY: 5.0}}))

            # Call with protocol info, should not give error
            service_data1 = {'protocol': 'test11',
                             'value': 42}
            service_data2 = {'protocol': 'test22',
                             'value': 42}
            self.hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                    service_data=service_data1,
                                    blocking=True)
            self.hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                    service_data=service_data2,
                                    blocking=True)
            service_data1['protocol'] = [service_data1['protocol']]
            service_data2['protocol'] = [service_data2['protocol']]

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED,
                               {ha.ATTR_NOW: dt_util.utcnow()})
            self.hass.block_till_done()
            error_log_call = mock_pilight_error.call_args_list[-1]
            self.assertTrue(str(service_data1) in str(error_log_call))

            new_time = dt_util.utcnow() + timedelta(seconds=5)
            self.hass.bus.fire(ha.EVENT_TIME_CHANGED,
                               {ha.ATTR_NOW: new_time})
            self.hass.block_till_done()
            error_log_call = mock_pilight_error.call_args_list[-1]
            self.assertTrue(str(service_data2) in str(error_log_call))

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('tests.components.test_pilight._LOGGER.error')
    def test_start_stop(self, mock_pilight_error):
        """Check correct startup and stop of pilight daemon."""
        with assert_setup_component(4):
            self.assertTrue(setup_component(
                self.hass, pilight.DOMAIN, {pilight.DOMAIN: {}}))

            # Test startup
            self.hass.start()
            self.hass.block_till_done()
            error_log_call = mock_pilight_error.call_args_list[-2]
            self.assertTrue(
                'PilightDaemonSim callback' in str(error_log_call))
            error_log_call = mock_pilight_error.call_args_list[-1]
            self.assertTrue(
                'PilightDaemonSim start' in str(error_log_call))

            # Test stop
            self.skip_teardown_stop = True
            self.hass.stop()
            error_log_call = mock_pilight_error.call_args_list[-1]
            self.assertTrue(
                'PilightDaemonSim stop' in str(error_log_call))

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('homeassistant.core._LOGGER.info')
    def test_receive_code(self, mock_info):
        """Check if code receiving via pilight daemon works."""
        with assert_setup_component(4):
            self.assertTrue(setup_component(
                self.hass, pilight.DOMAIN, {pilight.DOMAIN: {}}))

            # Test startup
            self.hass.start()
            self.hass.block_till_done()

            expected_message = dict(
                {'protocol': PilightDaemonSim.test_message['protocol'],
                 'uuid': PilightDaemonSim.test_message['uuid']},
                **PilightDaemonSim.test_message['message'])
            error_log_call = mock_info.call_args_list[-1]

            # Check if all message parts are put on event bus
            for key, value in expected_message.items():
                self.assertTrue(str(key) in str(error_log_call))
                self.assertTrue(str(value) in str(error_log_call))

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('homeassistant.core._LOGGER.info')
    def test_whitelist_exact_match(self, mock_info):
        """Check whitelist filter with matched data."""
        with assert_setup_component(4):
            whitelist = {
                'protocol': [PilightDaemonSim.test_message['protocol']],
                'uuid': [PilightDaemonSim.test_message['uuid']],
                'id': [PilightDaemonSim.test_message['message']['id']],
                'unit': [PilightDaemonSim.test_message['message']['unit']]}
            self.assertTrue(setup_component(
                self.hass, pilight.DOMAIN,
                {pilight.DOMAIN: {"whitelist": whitelist}}))

            self.hass.start()
            self.hass.block_till_done()

            expected_message = dict(
                {'protocol': PilightDaemonSim.test_message['protocol'],
                 'uuid': PilightDaemonSim.test_message['uuid']},
                **PilightDaemonSim.test_message['message'])
            info_log_call = mock_info.call_args_list[-1]

            # Check if all message parts are put on event bus
            for key, value in expected_message.items():
                self.assertTrue(str(key) in str(info_log_call))
                self.assertTrue(str(value) in str(info_log_call))

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('homeassistant.core._LOGGER.info')
    def test_whitelist_partial_match(self, mock_info):
        """Check whitelist filter with partially matched data, should work."""
        with assert_setup_component(4):
            whitelist = {
                'protocol': [PilightDaemonSim.test_message['protocol']],
                'id': [PilightDaemonSim.test_message['message']['id']]}
            self.assertTrue(setup_component(
                self.hass, pilight.DOMAIN,
                {pilight.DOMAIN: {"whitelist": whitelist}}))

            self.hass.start()
            self.hass.block_till_done()

            expected_message = dict(
                {'protocol': PilightDaemonSim.test_message['protocol'],
                 'uuid': PilightDaemonSim.test_message['uuid']},
                **PilightDaemonSim.test_message['message'])
            info_log_call = mock_info.call_args_list[-1]

            # Check if all message parts are put on event bus
            for key, value in expected_message.items():
                self.assertTrue(str(key) in str(info_log_call))
                self.assertTrue(str(value) in str(info_log_call))

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('homeassistant.core._LOGGER.info')
    def test_whitelist_or_match(self, mock_info):
        """Check whitelist filter with several subsection, should work."""
        with assert_setup_component(4):
            whitelist = {
                'protocol': [PilightDaemonSim.test_message['protocol'],
                             'other_protocol'],
                'id': [PilightDaemonSim.test_message['message']['id']]}
            self.assertTrue(setup_component(
                self.hass, pilight.DOMAIN,
                {pilight.DOMAIN: {"whitelist": whitelist}}))

            self.hass.start()
            self.hass.block_till_done()

            expected_message = dict(
                {'protocol': PilightDaemonSim.test_message['protocol'],
                 'uuid': PilightDaemonSim.test_message['uuid']},
                **PilightDaemonSim.test_message['message'])
            info_log_call = mock_info.call_args_list[-1]

            # Check if all message parts are put on event bus
            for key, value in expected_message.items():
                self.assertTrue(str(key) in str(info_log_call))
                self.assertTrue(str(value) in str(info_log_call))

    @patch('pilight.pilight.Client', PilightDaemonSim)
    @patch('homeassistant.core._LOGGER.info')
    def test_whitelist_no_match(self, mock_info):
        """Check whitelist filter with unmatched data, should not work."""
        with assert_setup_component(4):
            whitelist = {
                'protocol': ['wrong_protocol'],
                'id': [PilightDaemonSim.test_message['message']['id']]}
            self.assertTrue(setup_component(
                self.hass, pilight.DOMAIN,
                {pilight.DOMAIN: {"whitelist": whitelist}}))

            self.hass.start()
            self.hass.block_till_done()

            info_log_call = mock_info.call_args_list[-1]

            self.assertFalse('Event pilight_received' in info_log_call)


class TestPilightCallrateThrottler(unittest.TestCase):
    """Test the Throttler used to throttle calls to send_code."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_call_rate_delay_throttle_disabled(self):
        """Test that the limiter is a noop if no delay set."""
        runs = []

        limit = pilight.CallRateDelayThrottle(self.hass, 0.0)
        action = limit.limited(lambda x: runs.append(x))

        for i in range(3):
            action(i)

        self.assertEqual(runs, [0, 1, 2])

    def test_call_rate_delay_throttle_enabled(self):
        """Test that throttling actually work."""
        runs = []
        delay = 5.0

        limit = pilight.CallRateDelayThrottle(self.hass, delay)
        action = limit.limited(lambda x: runs.append(x))

        for i in range(3):
            action(i)

        self.assertEqual(runs, [])

        exp = []
        now = dt_util.utcnow()
        for i in range(3):
            exp.append(i)
            shifted_time = now + (timedelta(seconds=delay + 0.1) * i)
            self.hass.bus.fire(ha.EVENT_TIME_CHANGED,
                               {ha.ATTR_NOW: shifted_time})
            self.hass.block_till_done()
            self.assertEqual(runs, exp)
