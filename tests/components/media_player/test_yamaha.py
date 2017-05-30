"""The tests for the Yamaha Media player platform."""
import unittest
import xml.etree.ElementTree as ET

import rxv


def sample_content(name):
    """Read content into a string from a file."""
    with open('tests/components/media_player/yamaha_samples/%s' % name,
              encoding='utf-8') as content:
        return content.read()


class FakeYamaha(rxv.rxv.RXV):
    """Fake Yamaha receiver.

    This inherits from RXV but overrides methods for testing that
    would normally have hit the network. This makes it easier to
    ensure that usage of the rxv library by HomeAssistant is as we'd
    expect.
    """

    _fake_input = 'HDMI1'

    def _discover_features(self):
        """Fake the discovery feature."""
        self._desc_xml = ET.fromstring(sample_content('desc.xml'))

    @property
    def input(self):
        """A fake input for the reciever."""
        return self._fake_input

    @input.setter
    def input(self, input_name):
        """Set the input for the fake receiver."""
        assert input_name in self.inputs()
        self._fake_input = input_name

    def inputs(self):
        """All inputs of the the fake receiver."""
        return {'AUDIO1': None,
                'AUDIO2': None,
                'AV1': None,
                'AV2': None,
                'AV3': None,
                'AV4': None,
                'AV5': None,
                'AV6': None,
                'AirPlay': 'AirPlay',
                'HDMI1': None,
                'HDMI2': None,
                'HDMI3': None,
                'HDMI4': None,
                'HDMI5': None,
                'NET RADIO': 'NET_RADIO',
                'Pandora': 'Pandora',
                'Rhapsody': 'Rhapsody',
                'SERVER': 'SERVER',
                'SiriusXM': 'SiriusXM',
                'Spotify': 'Spotify',
                'TUNER': 'Tuner',
                'USB': 'USB',
                'V-AUX': None,
                'iPod (USB)': 'iPod_USB'}


# pylint: disable=no-member, invalid-name
class TestYamaha(unittest.TestCase):
    """Test the media_player yamaha module."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        super(TestYamaha, self).setUp()
        self.rec = FakeYamaha("http://10.0.0.0:80/YamahaRemoteControl/ctrl")

    def test_get_playback_support(self):
        """Test the playback."""
        rec = self.rec
        support = rec.get_playback_support()
        self.assertFalse(support.play)
        self.assertFalse(support.pause)
        self.assertFalse(support.stop)
        self.assertFalse(support.skip_f)
        self.assertFalse(support.skip_r)

        rec.input = 'NET RADIO'
        support = rec.get_playback_support()
        self.assertTrue(support.play)
        self.assertFalse(support.pause)
        self.assertTrue(support.stop)
        self.assertFalse(support.skip_f)
        self.assertFalse(support.skip_r)
