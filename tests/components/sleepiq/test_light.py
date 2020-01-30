"""The tests for SleepIQ light platform."""
import asyncio
import unittest
from unittest.mock import MagicMock

import requests_mock

import homeassistant.components.sleepiq.light as sleepiq
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant
from tests.components.sleepiq.test_init import mock_responses


class TestSleepIQLightSetup(unittest.TestCase):
    """Tests the SleepIQ Light platform."""

    DEVICES = []

    def add_entities(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.username = "foo"
        self.password = "bar"
        self.config = {"username": self.username, "password": self.password}
        self.DEVICES = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test for successfully setting up the SleepIQ platform."""
        mock_responses(mock)

        assert setup_component(self.hass, "sleepiq", {"sleepiq": self.config})

        sleepiq.setup_platform(self.hass, self.config, self.add_entities, None)
        assert not len(self.DEVICES)

        sleepiq.setup_platform(self.hass, self.config, self.add_entities, MagicMock())
        assert 4 == len(self.DEVICES)

        left_night_stand = self.DEVICES[0]
        assert "SleepNumber ILE Left Night Stand" == left_night_stand.name
        assert "off" == left_night_stand.state

        right_night_stand = self.DEVICES[1]
        assert "SleepNumber ILE Right Night Stand" == right_night_stand.name
        assert "off" == right_night_stand.state

        right_night_light = self.DEVICES[2]
        assert "SleepNumber ILE Right Night Light" == right_night_light.name
        assert "off" == right_night_light.state

        left_night_light = self.DEVICES[3]
        assert "SleepNumber ILE Left Night Light" == left_night_light.name
        assert "off" == left_night_light.state


class TestSleepIQLight(unittest.TestCase):
    """Tests for functionality of the lights platform."""

    DEVICES = []

    def add_entities(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.username = "foo"
        self.password = "bar"
        self.config = {"username": self.username, "password": self.password}
        self.DEVICES = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_turn_on(self, mock):
        """Test turning on a light."""
        mock_responses(mock)

        sleepiq.setup_platform(self.hass, self.config, self.add_entities, MagicMock())

        left_night_stand = self.DEVICES[0]
        asyncio.run_coroutine_threadsafe(
            sleepiq.SleepNumberLight.async_turn_on(left_night_stand), self.hass.loop
        )

        assert left_night_stand.state is not None

    @requests_mock.Mocker()
    def test_turn_off(self, mock):
        """Test turning off a light."""
        mock_responses(mock)

        sleepiq.setup_platform(self.hass, self.config, self.add_entities, MagicMock())

        left_night_stand = self.DEVICES[0]

        asyncio.run_coroutine_threadsafe(
            sleepiq.SleepNumberLight.async_turn_off(left_night_stand), self.hass.loop
        )

        assert left_night_stand.state == "off"

    @requests_mock.Mocker()
    def test_update(self, mock):
        """Test that the update function leaves the lights with a measureable state."""
        mock_responses(mock)

        sleepiq.setup_platform(self.hass, self.config, self.add_entities, MagicMock())

        left_night_stand = self.DEVICES[0]
        sleepiq.SleepNumberLight.update(left_night_stand)
        assert left_night_stand.state is not None
