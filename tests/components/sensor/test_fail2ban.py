"""The tests for local file sensor platform."""
import unittest
from unittest.mock import Mock, patch

from datetime import timedelta
from mock_open import MockOpen

from homeassistant.setup import setup_component
from homeassistant.components.sensor.fail2ban import (
    BanSensor, BanLogParser, STATE_CURRENT_BANS, STATE_ALL_BANS
)

from tests.common import get_test_home_assistant, assert_setup_component


def fake_log(log_key):
    """Return a fake fail2ban log."""
    fake_log_dict = {
        'single_ban': (
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Ban 111.111.111.111'
        ),
        'multi_ban': (
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Ban 111.111.111.111\n'
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Ban 222.222.222.222'
        ),
        'multi_jail': (
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Ban 111.111.111.111\n'
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_two] Ban 222.222.222.222'
        ),
        'unban_all': (
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Ban 111.111.111.111\n'
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Unban 111.111.111.111\n'
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Ban 222.222.222.222\n'
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Unban 222.222.222.222'
        ),
        'unban_one': (
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Ban 111.111.111.111\n'
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Ban 222.222.222.222\n'
            '2017-01-01 12:23:35 fail2ban.actions [111]: '
            'NOTICE [jail_one] Unban 111.111.111.111'
        )
    }
    return fake_log_dict[log_key]


class TestBanSensor(unittest.TestCase):
    """Test the fail2ban sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('os.path.isfile', Mock(return_value=True))
    def test_setup(self):
        """Test that sensor can be setup."""
        config = {
            'sensor': {
                'platform': 'fail2ban',
                'jails': ['jail_one']
            }
        }
        mock_fh = MockOpen()
        with patch('homeassistant.components.sensor.fail2ban.open', mock_fh,
                   create=True):
            assert setup_component(self.hass, 'sensor', config)
            self.hass.block_till_done()
        assert_setup_component(1, 'sensor')

    @patch('os.path.isfile', Mock(return_value=True))
    def test_multi_jails(self):
        """Test that multiple jails can be set up as sensors.."""
        config = {
            'sensor': {
                'platform': 'fail2ban',
                'jails': ['jail_one', 'jail_two']
            }
        }
        mock_fh = MockOpen()
        with patch('homeassistant.components.sensor.fail2ban.open', mock_fh,
                   create=True):
            assert setup_component(self.hass, 'sensor', config)
            self.hass.block_till_done()
        assert_setup_component(2, 'sensor')

    def test_single_ban(self):
        """Test that log is parsed correctly for single ban."""
        log_parser = BanLogParser(timedelta(seconds=-1), '/tmp')
        sensor = BanSensor('fail2ban', 'jail_one', log_parser)
        assert sensor.name == 'fail2ban jail_one'
        mock_fh = MockOpen(read_data=fake_log('single_ban'))
        with patch('homeassistant.components.sensor.fail2ban.open', mock_fh,
                   create=True):
            sensor.update()

        assert sensor.state == '111.111.111.111'
        assert \
            sensor.state_attributes[STATE_CURRENT_BANS] == ['111.111.111.111']
        assert \
            sensor.state_attributes[STATE_ALL_BANS] == ['111.111.111.111']

    def test_multiple_ban(self):
        """Test that log is parsed correctly for multiple ban."""
        log_parser = BanLogParser(timedelta(seconds=-1), '/tmp')
        sensor = BanSensor('fail2ban', 'jail_one', log_parser)
        assert sensor.name == 'fail2ban jail_one'
        mock_fh = MockOpen(read_data=fake_log('multi_ban'))
        with patch('homeassistant.components.sensor.fail2ban.open', mock_fh,
                   create=True):
            sensor.update()

        assert sensor.state == '222.222.222.222'
        assert sensor.state_attributes[STATE_CURRENT_BANS] == \
            ['111.111.111.111', '222.222.222.222']
        assert sensor.state_attributes[STATE_ALL_BANS] == \
            ['111.111.111.111', '222.222.222.222']

    def test_unban_all(self):
        """Test that log is parsed correctly when unbanning."""
        log_parser = BanLogParser(timedelta(seconds=-1), '/tmp')
        sensor = BanSensor('fail2ban', 'jail_one', log_parser)
        assert sensor.name == 'fail2ban jail_one'
        mock_fh = MockOpen(read_data=fake_log('unban_all'))
        with patch('homeassistant.components.sensor.fail2ban.open', mock_fh,
                   create=True):
            sensor.update()

        assert sensor.state == 'None'
        assert sensor.state_attributes[STATE_CURRENT_BANS] == []
        assert sensor.state_attributes[STATE_ALL_BANS] == \
            ['111.111.111.111', '222.222.222.222']

    def test_unban_one(self):
        """Test that log is parsed correctly when unbanning one ip."""
        log_parser = BanLogParser(timedelta(seconds=-1), '/tmp')
        sensor = BanSensor('fail2ban', 'jail_one', log_parser)
        assert sensor.name == 'fail2ban jail_one'
        mock_fh = MockOpen(read_data=fake_log('unban_one'))
        with patch('homeassistant.components.sensor.fail2ban.open', mock_fh,
                   create=True):
            sensor.update()

        assert sensor.state == '222.222.222.222'
        assert sensor.state_attributes[STATE_CURRENT_BANS] == \
            ['222.222.222.222']
        assert sensor.state_attributes[STATE_ALL_BANS] == \
            ['111.111.111.111', '222.222.222.222']

    def test_multi_jail(self):
        """Test that log is parsed correctly when using multiple jails."""
        log_parser = BanLogParser(timedelta(seconds=-1), '/tmp')
        sensor1 = BanSensor('fail2ban', 'jail_one', log_parser)
        sensor2 = BanSensor('fail2ban', 'jail_two', log_parser)
        assert sensor1.name == 'fail2ban jail_one'
        assert sensor2.name == 'fail2ban jail_two'
        mock_fh = MockOpen(read_data=fake_log('multi_jail'))
        with patch('homeassistant.components.sensor.fail2ban.open', mock_fh,
                   create=True):
            sensor1.update()
            sensor2.update()

        assert sensor1.state == '111.111.111.111'
        assert \
            sensor1.state_attributes[STATE_CURRENT_BANS] == ['111.111.111.111']
        assert sensor1.state_attributes[STATE_ALL_BANS] == ['111.111.111.111']
        assert sensor2.state == '222.222.222.222'
        assert \
            sensor2.state_attributes[STATE_CURRENT_BANS] == ['222.222.222.222']
        assert sensor2.state_attributes[STATE_ALL_BANS] == ['222.222.222.222']

    def test_ban_active_after_update(self):
        """Test that ban persists after subsequent update."""
        log_parser = BanLogParser(timedelta(seconds=-1), '/tmp')
        sensor = BanSensor('fail2ban', 'jail_one', log_parser)
        assert sensor.name == 'fail2ban jail_one'
        mock_fh = MockOpen(read_data=fake_log('single_ban'))
        with patch('homeassistant.components.sensor.fail2ban.open', mock_fh,
                   create=True):
            sensor.update()
            assert sensor.state == '111.111.111.111'
            sensor.update()
            assert sensor.state == '111.111.111.111'
        assert \
            sensor.state_attributes[STATE_CURRENT_BANS] == ['111.111.111.111']
        assert sensor.state_attributes[STATE_ALL_BANS] == ['111.111.111.111']
