"""The tests for the ASUSWRT device tracker platform."""
import os
from datetime import timedelta
import unittest
from unittest import mock

import voluptuous as vol
from future.backports import socket

from homeassistant.setup import setup_component
from homeassistant.components import device_tracker
from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME, CONF_TRACK_NEW, CONF_NEW_DEVICE_DEFAULTS,
    CONF_AWAY_HIDE)
from homeassistant.components.device_tracker.asuswrt import (
    CONF_PROTOCOL, CONF_MODE, CONF_PUB_KEY, DOMAIN, _ARP_REGEX,
    CONF_PORT, PLATFORM_SCHEMA, Device, get_scanner, AsusWrtDeviceScanner,
    _parse_lines, SshConnection, TelnetConnection)
from homeassistant.const import (CONF_PLATFORM, CONF_PASSWORD, CONF_USERNAME,
                                 CONF_HOST)

from tests.common import (
    get_test_home_assistant, get_test_config_dir, assert_setup_component,
    mock_component)

FAKEFILE = None

VALID_CONFIG_ROUTER_SSH = {DOMAIN: {
    CONF_PLATFORM: 'asuswrt',
    CONF_HOST: 'fake_host',
    CONF_USERNAME: 'fake_user',
    CONF_PROTOCOL: 'ssh',
    CONF_MODE: 'router',
    CONF_PORT: '22'
}
}

WL_DATA = [
    'assoclist 01:02:03:04:06:08\r',
    'assoclist 08:09:10:11:12:14\r',
    'assoclist 08:09:10:11:12:15\r'
]

WL_DEVICES = {
    '01:02:03:04:06:08': Device(
        mac='01:02:03:04:06:08', ip=None, name=None),
    '08:09:10:11:12:14': Device(
        mac='08:09:10:11:12:14', ip=None, name=None),
    '08:09:10:11:12:15': Device(
        mac='08:09:10:11:12:15', ip=None, name=None)
}

ARP_DATA = [
    '? (123.123.123.125) at 01:02:03:04:06:08 [ether]  on eth0\r',
    '? (123.123.123.126) at 08:09:10:11:12:14 [ether]  on br0\r'
    '? (123.123.123.127) at <incomplete>  on br0\r'
]

ARP_DEVICES = {
    '01:02:03:04:06:08': Device(
        mac='01:02:03:04:06:08', ip='123.123.123.125', name=None),
    '08:09:10:11:12:14': Device(
        mac='08:09:10:11:12:14', ip='123.123.123.126', name=None)
}

NEIGH_DATA = [
    '123.123.123.125 dev eth0 lladdr 01:02:03:04:06:08 REACHABLE\r',
    '123.123.123.126 dev br0 lladdr 08:09:10:11:12:14 STALE\r'
    '123.123.123.127 dev br0  FAILED\r'
]

NEIGH_DEVICES = {
    '01:02:03:04:06:08': Device(
        mac='01:02:03:04:06:08', ip='123.123.123.125', name=None),
    '08:09:10:11:12:14': Device(
        mac='08:09:10:11:12:14', ip='123.123.123.126', name=None)
}

LEASES_DATA = [
    '51910 01:02:03:04:06:08 123.123.123.125 TV 01:02:03:04:06:08\r',
    '79986 01:02:03:04:06:10 123.123.123.127 android 01:02:03:04:06:15\r',
    '23523 08:09:10:11:12:14 123.123.123.126 * 08:09:10:11:12:14\r',
]

LEASES_DEVICES = {
    '01:02:03:04:06:08': Device(
        mac='01:02:03:04:06:08', ip='123.123.123.125', name='TV'),
    '08:09:10:11:12:14': Device(
        mac='08:09:10:11:12:14', ip='123.123.123.126', name='')
}

WAKE_DEVICES = {
    '01:02:03:04:06:08': Device(
        mac='01:02:03:04:06:08', ip='123.123.123.125', name='TV'),
    '08:09:10:11:12:14': Device(
        mac='08:09:10:11:12:14', ip='123.123.123.126', name='')
}

WAKE_DEVICES_AP = {
    '01:02:03:04:06:08': Device(
        mac='01:02:03:04:06:08', ip='123.123.123.125', name=None),
    '08:09:10:11:12:14': Device(
        mac='08:09:10:11:12:14', ip='123.123.123.126', name=None)
}


def setup_module():
    """Setup the test module."""
    global FAKEFILE
    FAKEFILE = get_test_config_dir('fake_file')
    with open(FAKEFILE, 'w') as out:
        out.write(' ')


def teardown_module():
    """Tear down the module."""
    os.remove(FAKEFILE)


class TestComponentsDeviceTrackerASUSWRT(unittest.TestCase):
    """Tests for the ASUSWRT device tracker platform."""

    hass = None

    def setup_method(self, _):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'zone')

    def teardown_method(self, _):
        """Stop everything that was started."""
        self.hass.stop()
        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def test_parse_lines_wrong_input(self):
        """Testing parse lines."""
        output = _parse_lines("asdf asdfdfsafad", _ARP_REGEX)
        self.assertEqual(output, [])

    def test_get_device_name(self):
        """Test for getting name."""
        scanner = get_scanner(self.hass, VALID_CONFIG_ROUTER_SSH)
        scanner.last_results = WAKE_DEVICES
        self.assertEqual('TV', scanner.get_device_name('01:02:03:04:06:08'))
        self.assertEqual(None, scanner.get_device_name('01:02:03:04:08:08'))

    def test_scan_devices(self):
        """Test for scan devices."""
        scanner = get_scanner(self.hass, VALID_CONFIG_ROUTER_SSH)
        scanner.last_results = WAKE_DEVICES
        self.assertEqual(list(WAKE_DEVICES), scanner.scan_devices())

    def test_password_or_pub_key_required(self): \
            # pylint: disable=invalid-name
        """Test creating an AsusWRT scanner without a pass or pubkey."""
        with assert_setup_component(0, DOMAIN):
            assert setup_component(
                self.hass, DOMAIN, {DOMAIN: {
                    CONF_PLATFORM: 'asuswrt',
                    CONF_HOST: 'fake_host',
                    CONF_USERNAME: 'fake_user',
                    CONF_PROTOCOL: 'ssh'
                }})

    @mock.patch(
        'homeassistant.components.device_tracker.asuswrt.AsusWrtDeviceScanner',
        return_value=mock.MagicMock())
    def test_get_scanner_with_password_no_pubkey(self, asuswrt_mock): \
            # pylint: disable=invalid-name
        """Test creating an AsusWRT scanner with a password and no pubkey."""
        conf_dict = {
            DOMAIN: {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                CONF_PASSWORD: 'fake_pass',
                CONF_TRACK_NEW: True,
                CONF_CONSIDER_HOME: timedelta(seconds=180),
                CONF_NEW_DEVICE_DEFAULTS: {
                    CONF_TRACK_NEW: True,
                    CONF_AWAY_HIDE: False
                }
            }
        }

        with assert_setup_component(1, DOMAIN):
            assert setup_component(self.hass, DOMAIN, conf_dict)

        conf_dict[DOMAIN][CONF_MODE] = 'router'
        conf_dict[DOMAIN][CONF_PROTOCOL] = 'ssh'
        conf_dict[DOMAIN][CONF_PORT] = 22
        self.assertEqual(asuswrt_mock.call_count, 1)
        self.assertEqual(asuswrt_mock.call_args, mock.call(conf_dict[DOMAIN]))

    @mock.patch(
        'homeassistant.components.device_tracker.asuswrt.AsusWrtDeviceScanner',
        return_value=mock.MagicMock())
    def test_get_scanner_with_pubkey_no_password(self, asuswrt_mock): \
            # pylint: disable=invalid-name
        """Test creating an AsusWRT scanner with a pubkey and no password."""
        conf_dict = {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                CONF_PUB_KEY: FAKEFILE,
                CONF_TRACK_NEW: True,
                CONF_CONSIDER_HOME: timedelta(seconds=180),
                CONF_NEW_DEVICE_DEFAULTS: {
                    CONF_TRACK_NEW: True,
                    CONF_AWAY_HIDE: False
                }
            }
        }

        with assert_setup_component(1, DOMAIN):
            assert setup_component(self.hass, DOMAIN, conf_dict)

        conf_dict[DOMAIN][CONF_MODE] = 'router'
        conf_dict[DOMAIN][CONF_PROTOCOL] = 'ssh'
        conf_dict[DOMAIN][CONF_PORT] = 22
        self.assertEqual(asuswrt_mock.call_count, 1)
        self.assertEqual(asuswrt_mock.call_args, mock.call(conf_dict[DOMAIN]))

    def test_ssh_login_with_pub_key(self):
        """Test that login is done with pub_key when configured to."""
        ssh = mock.MagicMock()
        ssh_mock = mock.patch('pexpect.pxssh.pxssh', return_value=ssh)
        ssh_mock.start()
        self.addCleanup(ssh_mock.stop)
        conf_dict = PLATFORM_SCHEMA({
            CONF_PLATFORM: 'asuswrt',
            CONF_HOST: 'fake_host',
            CONF_USERNAME: 'fake_user',
            CONF_PUB_KEY: FAKEFILE
        })
        update_mock = mock.patch(
            'homeassistant.components.device_tracker.asuswrt.'
            'AsusWrtDeviceScanner.get_asuswrt_data')
        update_mock.start()
        self.addCleanup(update_mock.stop)
        asuswrt = device_tracker.asuswrt.AsusWrtDeviceScanner(conf_dict)
        asuswrt.connection.run_command('ls')
        self.assertEqual(ssh.login.call_count, 1)
        self.assertEqual(
            ssh.login.call_args,
            mock.call('fake_host', 'fake_user',
                      ssh_key=FAKEFILE, port=22)
        )

    def test_ssh_login_with_password(self):
        """Test that login is done with password when configured to."""
        ssh = mock.MagicMock()
        ssh_mock = mock.patch('pexpect.pxssh.pxssh', return_value=ssh)
        ssh_mock.start()
        self.addCleanup(ssh_mock.stop)
        conf_dict = PLATFORM_SCHEMA({
            CONF_PLATFORM: 'asuswrt',
            CONF_HOST: 'fake_host',
            CONF_USERNAME: 'fake_user',
            CONF_PASSWORD: 'fake_pass'
        })
        update_mock = mock.patch(
            'homeassistant.components.device_tracker.asuswrt.'
            'AsusWrtDeviceScanner.get_asuswrt_data')
        update_mock.start()
        self.addCleanup(update_mock.stop)
        asuswrt = device_tracker.asuswrt.AsusWrtDeviceScanner(conf_dict)
        asuswrt.connection.run_command('ls')
        self.assertEqual(ssh.login.call_count, 1)
        self.assertEqual(
            ssh.login.call_args,
            mock.call('fake_host', 'fake_user',
                      password='fake_pass', port=22)
        )

    def test_ssh_login_without_password_or_pubkey(self): \
            # pylint: disable=invalid-name
        """Test that login is not called without password or pub_key."""
        ssh = mock.MagicMock()
        ssh_mock = mock.patch('pexpect.pxssh.pxssh', return_value=ssh)
        ssh_mock.start()
        self.addCleanup(ssh_mock.stop)

        conf_dict = {
            CONF_PLATFORM: 'asuswrt',
            CONF_HOST: 'fake_host',
            CONF_USERNAME: 'fake_user',
        }

        with self.assertRaises(vol.Invalid):
            conf_dict = PLATFORM_SCHEMA(conf_dict)

        update_mock = mock.patch(
            'homeassistant.components.device_tracker.asuswrt.'
            'AsusWrtDeviceScanner.get_asuswrt_data')
        update_mock.start()
        self.addCleanup(update_mock.stop)

        with assert_setup_component(0, DOMAIN):
            assert setup_component(self.hass, DOMAIN,
                                   {DOMAIN: conf_dict})
        ssh.login.assert_not_called()

    def test_telnet_login_with_password(self):
        """Test that login is done with password when configured to."""
        telnet = mock.MagicMock()
        telnet_mock = mock.patch('telnetlib.Telnet', return_value=telnet)
        telnet_mock.start()
        self.addCleanup(telnet_mock.stop)
        conf_dict = PLATFORM_SCHEMA({
            CONF_PLATFORM: 'asuswrt',
            CONF_PROTOCOL: 'telnet',
            CONF_HOST: 'fake_host',
            CONF_USERNAME: 'fake_user',
            CONF_PASSWORD: 'fake_pass'
        })
        update_mock = mock.patch(
            'homeassistant.components.device_tracker.asuswrt.'
            'AsusWrtDeviceScanner.get_asuswrt_data')
        update_mock.start()
        self.addCleanup(update_mock.stop)
        asuswrt = device_tracker.asuswrt.AsusWrtDeviceScanner(conf_dict)
        asuswrt.connection.run_command('ls')
        self.assertEqual(telnet.read_until.call_count, 4)
        self.assertEqual(telnet.write.call_count, 3)
        self.assertEqual(
            telnet.read_until.call_args_list[0],
            mock.call(b'login: ')
        )
        self.assertEqual(
            telnet.write.call_args_list[0],
            mock.call(b'fake_user\n')
        )
        self.assertEqual(
            telnet.read_until.call_args_list[1],
            mock.call(b'Password: ')
        )
        self.assertEqual(
            telnet.write.call_args_list[1],
            mock.call(b'fake_pass\n')
        )
        self.assertEqual(
            telnet.read_until.call_args_list[2],
            mock.call(b'#')
        )

    def test_telnet_login_without_password(self): \
            # pylint: disable=invalid-name
        """Test that login is not called without password or pub_key."""
        telnet = mock.MagicMock()
        telnet_mock = mock.patch('telnetlib.Telnet', return_value=telnet)
        telnet_mock.start()
        self.addCleanup(telnet_mock.stop)

        conf_dict = {
            CONF_PLATFORM: 'asuswrt',
            CONF_PROTOCOL: 'telnet',
            CONF_HOST: 'fake_host',
            CONF_USERNAME: 'fake_user',
        }

        with self.assertRaises(vol.Invalid):
            conf_dict = PLATFORM_SCHEMA(conf_dict)

        update_mock = mock.patch(
            'homeassistant.components.device_tracker.asuswrt.'
            'AsusWrtDeviceScanner.get_asuswrt_data')
        update_mock.start()
        self.addCleanup(update_mock.stop)

        with assert_setup_component(0, DOMAIN):
            assert setup_component(self.hass, DOMAIN,
                                   {DOMAIN: conf_dict})
        telnet.login.assert_not_called()

    def test_get_asuswrt_data(self):
        """Test aususwrt data fetch."""
        scanner = get_scanner(self.hass, VALID_CONFIG_ROUTER_SSH)
        scanner._get_wl = mock.Mock()
        scanner._get_arp = mock.Mock()
        scanner._get_neigh = mock.Mock()
        scanner._get_leases = mock.Mock()
        scanner._get_wl.return_value = WL_DEVICES
        scanner._get_arp.return_value = ARP_DEVICES
        scanner._get_neigh.return_value = NEIGH_DEVICES
        scanner._get_leases.return_value = LEASES_DEVICES
        self.assertEqual(WAKE_DEVICES, scanner.get_asuswrt_data())

    def test_get_asuswrt_data_ap(self):
        """Test for get asuswrt_data in ap mode."""
        conf = VALID_CONFIG_ROUTER_SSH.copy()[DOMAIN]
        conf[CONF_MODE] = 'ap'
        scanner = AsusWrtDeviceScanner(conf)
        scanner._get_wl = mock.Mock()
        scanner._get_arp = mock.Mock()
        scanner._get_neigh = mock.Mock()
        scanner._get_leases = mock.Mock()
        scanner._get_wl.return_value = WL_DEVICES
        scanner._get_arp.return_value = ARP_DEVICES
        scanner._get_neigh.return_value = NEIGH_DEVICES
        scanner._get_leases.return_value = LEASES_DEVICES
        self.assertEqual(WAKE_DEVICES_AP, scanner.get_asuswrt_data())

    def test_update_info(self):
        """Test for update info."""
        scanner = get_scanner(self.hass, VALID_CONFIG_ROUTER_SSH)
        scanner.get_asuswrt_data = mock.Mock()
        scanner.get_asuswrt_data.return_value = WAKE_DEVICES
        self.assertTrue(scanner._update_info())
        self.assertTrue(scanner.last_results, WAKE_DEVICES)
        scanner.success_init = False
        self.assertFalse(scanner._update_info())

    @mock.patch(
        'homeassistant.components.device_tracker.asuswrt.SshConnection')
    def test_get_wl(self, mocked_ssh):
        """Testing wl."""
        mocked_ssh.run_command.return_value = WL_DATA
        scanner = get_scanner(self.hass, VALID_CONFIG_ROUTER_SSH)
        scanner.connection = mocked_ssh
        self.assertEqual(WL_DEVICES, scanner._get_wl())
        mocked_ssh.run_command.return_value = ''
        self.assertEqual({}, scanner._get_wl())

    @mock.patch(
        'homeassistant.components.device_tracker.asuswrt.SshConnection')
    def test_get_arp(self, mocked_ssh):
        """Testing arp."""
        mocked_ssh.run_command.return_value = ARP_DATA

        scanner = get_scanner(self.hass, VALID_CONFIG_ROUTER_SSH)
        scanner.connection = mocked_ssh
        self.assertEqual(ARP_DEVICES, scanner._get_arp())
        mocked_ssh.run_command.return_value = ''
        self.assertEqual({}, scanner._get_arp())

    @mock.patch(
        'homeassistant.components.device_tracker.asuswrt.SshConnection')
    def test_get_neigh(self, mocked_ssh):
        """Testing neigh."""
        mocked_ssh.run_command.return_value = NEIGH_DATA

        scanner = get_scanner(self.hass, VALID_CONFIG_ROUTER_SSH)
        scanner.connection = mocked_ssh
        self.assertEqual(NEIGH_DEVICES, scanner._get_neigh(ARP_DEVICES.copy()))
        self.assertEqual(NEIGH_DEVICES, scanner._get_neigh({
            'UN:KN:WN:DE:VI:CE': Device('UN:KN:WN:DE:VI:CE', None, None),
        }))
        mocked_ssh.run_command.return_value = ''
        self.assertEqual({}, scanner._get_neigh(ARP_DEVICES.copy()))

    @mock.patch(
        'homeassistant.components.device_tracker.asuswrt.SshConnection')
    def test_get_leases(self, mocked_ssh):
        """Testing leases."""
        mocked_ssh.run_command.return_value = LEASES_DATA

        scanner = get_scanner(self.hass, VALID_CONFIG_ROUTER_SSH)
        scanner.connection = mocked_ssh
        self.assertEqual(
            LEASES_DEVICES, scanner._get_leases(NEIGH_DEVICES.copy()))
        mocked_ssh.run_command.return_value = ''
        self.assertEqual({}, scanner._get_leases(NEIGH_DEVICES.copy()))


class TestSshConnection(unittest.TestCase):
    """Testing SshConnection."""

    def setUp(self):
        """Setup test env."""
        self.connection = SshConnection(
            'fake', 'fake', 'fake', 'fake', 'fake', 'fake')
        self.connection._connected = True

    def test_run_command_exception_eof(self):
        """Testing exception in run_command."""
        from pexpect import exceptions
        self.connection._ssh = mock.Mock()
        self.connection._ssh.sendline = mock.Mock()
        self.connection._ssh.sendline.side_effect = exceptions.EOF('except')
        self.connection.run_command('test')
        self.assertFalse(self.connection._connected)
        self.assertIsNone(self.connection._ssh)

    def test_run_command_exception_pxssh(self):
        """Testing exception in run_command."""
        from pexpect import pxssh
        self.connection._ssh = mock.Mock()
        self.connection._ssh.sendline = mock.Mock()
        self.connection._ssh.sendline.side_effect = pxssh.ExceptionPxssh(
            'except')
        self.connection.run_command('test')
        self.assertFalse(self.connection._connected)
        self.assertIsNone(self.connection._ssh)

    def test_run_command_assertion_error(self):
        """Testing exception in run_command."""
        self.connection._ssh = mock.Mock()
        self.connection._ssh.sendline = mock.Mock()
        self.connection._ssh.sendline.side_effect = AssertionError('except')
        self.connection.run_command('test')
        self.assertFalse(self.connection._connected)
        self.assertIsNone(self.connection._ssh)


class TestTelnetConnection(unittest.TestCase):
    """Testing TelnetConnection."""

    def setUp(self):
        """Setup test env."""
        self.connection = TelnetConnection(
            'fake', 'fake', 'fake', 'fake', 'fake')
        self.connection._connected = True

    def test_run_command_exception_eof(self):
        """Testing EOFException in run_command."""
        self.connection._telnet = mock.Mock()
        self.connection._telnet.write = mock.Mock()
        self.connection._telnet.write.side_effect = EOFError('except')
        self.connection.run_command('test')
        self.assertFalse(self.connection._connected)

    def test_run_command_exception_connection_refused(self):
        """Testing ConnectionRefusedError in run_command."""
        self.connection._telnet = mock.Mock()
        self.connection._telnet.write = mock.Mock()
        self.connection._telnet.write.side_effect = ConnectionRefusedError(
            'except')
        self.connection.run_command('test')
        self.assertFalse(self.connection._connected)

    def test_run_command_exception_gaierror(self):
        """Testing socket.gaierror in run_command."""
        self.connection._telnet = mock.Mock()
        self.connection._telnet.write = mock.Mock()
        self.connection._telnet.write.side_effect = socket.gaierror('except')
        self.connection.run_command('test')
        self.assertFalse(self.connection._connected)

    def test_run_command_exception_oserror(self):
        """Testing OSError in run_command."""
        self.connection._telnet = mock.Mock()
        self.connection._telnet.write = mock.Mock()
        self.connection._telnet.write.side_effect = OSError('except')
        self.connection.run_command('test')
        self.assertFalse(self.connection._connected)
