"""The tests for the Kef Media player platform."""
import unittest
from unittest import mock
import json

from homeassistant.setup import setup_component
from homeassistant.components.media_player import kef, DOMAIN
from homeassistant.components.media_player.kef import (
    CONF_TURN_ON_SERVICE, CONF_TURN_ON_DATA
)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PLATFORM, STATE_OFF
)

from tests.common import get_test_home_assistant


class KefSpeakerMock:
    """Mock class for pykef lib."""

    def __init__(self, host, port):
        """Mock for KefSpeaker initializer."""
        self.__volume = 0.0
        self.__muted = False
        self.__source = None
        self.is_online = True
        self.host = host
        self.port = port

    def send_command(self, cmd):
        """Mock for send command to hardware."""
        pass

    @property
    def volume(self):
        """Mock for getting volume level. None if muted."""
        if not self.online:
            raise ConnectionRefusedError("Offline")
        return self.__volume if not self.__muted else None

    @volume.setter
    def volume(self, value):
        """Mock for setting volume level. None to mute."""
        if not self.online:
            raise ConnectionRefusedError("Offline")
        if value:
            self.__volume = max(0.0, min(1.0, value))
            self.send_command("volume {}".format(self.__volume))
        else:
            self.__muted = True
            self.send_command("mute")

    @property
    def source(self):
        """Mock for getting the input source of the speaker."""
        if not self.online:
            raise ConnectionRefusedError("Offline")
        return self.__source

    @source.setter
    def source(self, value):
        """Mock for setting the input source."""
        if not self.online:
            raise ConnectionRefusedError("Offline")
        self.__source = value

    @property
    def muted(self):
        """Mock for muted. True if muted, else False."""
        if not self.online:
            raise ConnectionRefusedError("Offline")
        return self.__muted

    @muted.setter
    def muted(self, value):
        """Mock for set muted."""
        if not self.online:
            raise ConnectionRefusedError("Offline")
        self.__muted = value

    @property
    def online(self):
        """Mock for get if speaker is online or not."""
        return self.is_online

    # pylint: disable=invalid-name
    def turnOff(self):
        """Mock for turn off the speaker."""
        if not self.online:
            raise ConnectionRefusedError("Offline")
        self.is_online = False
        return True

    # pylint: disable=invalid-name
    def increaseVolume(self, step=None):
        """Mock for increase volume."""
        if not self.online:
            raise ConnectionRefusedError("Offline")
        if not self.__muted:
            self.__volume = self.__volume + (step if step else 0.05)

    # pylint: disable=invalid-name
    def decreaseVolume(self, step=None):
        """Mock for decrease volume."""
        self.increaseVolume(-(step or 0.05))


def add_entities_factory(self):
    """Add devices factory."""
    def add_entities(devices, update_befor_add=False):
        """Fake add device."""
        self.devices += devices

    return add_entities


class TestKefMediaPlayer(unittest.TestCase):
    """Unit tests for kef component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.config = {
            DOMAIN: {
                CONF_PLATFORM: 'kef',
                CONF_HOST: '192.0.1.1',
            }
        }
        self.turn_on_config = {
            DOMAIN: {
                CONF_PLATFORM: 'kef',
                CONF_HOST: '192.0.1.1',
                CONF_NAME: 'speaker',
                CONF_TURN_ON_SERVICE: "homeassistant.turn_on",
                CONF_TURN_ON_DATA: "{}"
            }
        }
        self.devices = list()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('pykef.KefSpeaker', side_effect=KefSpeakerMock)
    def test_setup(self, kef_speaker):
        """Test a single device setup."""
        setup_component(self.hass, DOMAIN, self.config)
        devices = list(self.hass.data[DOMAIN].entities)
        self.assertEqual(len(devices), 1)
        kef_speaker.assert_called_once_with('192.0.1.1', 50001)

    @mock.patch('pykef.KefSpeaker', side_effect=KefSpeakerMock)
    def test_setup_with_turn_on_service(self, kef_speaker):
        """Test a single device with turn_on service in config."""
        setup_component(self.hass, DOMAIN, self.turn_on_config)
        devices = list(self.hass.data[DOMAIN].entities)
        self.assertEqual(len(devices), 1)

    @mock.patch('pykef.KefSpeaker', side_effect=KefSpeakerMock)
    def test_setup_while_offline(self, kef_speaker):
        """Test a single device while offline."""
        kef_speaker.online = mock.Mock(return_value=False)
        setup_component(self.hass, DOMAIN, self.config)
        devices = list(self.hass.data[DOMAIN].entities)
        self.assertEqual(len(devices), 1)
        kef_speaker.assert_called_once_with('192.0.1.1', 50001)

    @mock.patch('pykef.KefSpeaker', side_effect=KefSpeakerMock)
    def test_turn_off_service_call(self, kef_speaker):
        """Test turn off."""
        hass_mock = mock.Mock()
        kef.setup_platform(hass_mock, self.config[DOMAIN],
                           add_entities_factory(self))
        self.devices[0].update()
        self.devices[0].turn_off()
        self.assertEqual(self.devices[0].state, STATE_OFF)

    @mock.patch('pykef.KefSpeaker', side_effect=KefSpeakerMock)
    def test_turn_on_service_call(self, kef_speaker):
        """Test turn on service when configured."""
        hass_mock = mock.Mock()
        kef.setup_platform(hass_mock, self.turn_on_config[DOMAIN],
                           add_entities_factory(self))
        self.devices[0].update()
        self.devices[0].turn_off()
        self.devices[0].turn_on()
        hass_mock.services.call.assert_called_once_with(
            "homeassistant", "turn_on", json.loads("{}"), False)

    @mock.patch('pykef.KefSpeaker', side_effect=KefSpeakerMock)
    def test_turn_on_service_call_fail_if_already_online(self, kef_speaker):
        """Test turn on service when configured."""
        hass_mock = mock.Mock()
        kef.setup_platform(hass_mock, self.turn_on_config[DOMAIN],
                           add_entities_factory(self))
        self.devices[0].update()
        self.devices[0].turn_on()
        hass_mock.services.call.assert_not_called()

    @mock.patch('pykef.KefSpeaker', side_effect=KefSpeakerMock)
    def test_get_and_set_volume(self, kef_speaker):
        """Test get and set volume."""
        hass_mock = mock.Mock()
        kef.setup_platform(hass_mock, self.config[DOMAIN],
                           add_entities_factory(self))
        self.devices[0].update()
        self.devices[0].set_volume_level(0.4)
        self.assertEqual(self.devices[0].volume_level, 0.4)

    @mock.patch('pykef.KefSpeaker', side_effect=KefSpeakerMock)
    def test_inc_volume(self, kef_speaker):
        """Test increase the volume."""
        hass_mock = mock.Mock()
        kef.setup_platform(hass_mock, self.config[DOMAIN],
                           add_entities_factory(self))
        self.devices[0].update()
        self.devices[0].set_volume_level(0.4)
        self.assertEqual(self.devices[0].volume_level, 0.4)
        self.devices[0].volume_up()
        self.assertAlmostEqual(self.devices[0].volume_level, 0.45)

    @mock.patch('pykef.KefSpeaker', side_effect=KefSpeakerMock)
    def test_dec_volume(self, kef_speaker):
        """Test decrease the volume."""
        hass_mock = mock.Mock()
        kef.setup_platform(hass_mock, self.config[DOMAIN],
                           add_entities_factory(self))
        self.devices[0].update()
        self.devices[0].set_volume_level(0.4)
        self.assertEqual(self.devices[0].volume_level, 0.4)
        self.devices[0].volume_down()
        self.assertAlmostEqual(self.devices[0].volume_level, 0.35)
