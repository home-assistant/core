"""Test the parent Dyson component."""
import unittest
from unittest import mock

from homeassistant.components import dyson

from .common import load_mock_device

from tests.common import get_test_home_assistant


def _get_dyson_account_device_available():
    """Return a valid device provide by Dyson web services."""
    device = mock.Mock()
    load_mock_device(device)
    device.connect = mock.Mock(return_value=True)
    device.auto_connect = mock.Mock(return_value=True)
    return device


def _get_dyson_account_device_not_available():
    """Return an invalid device provide by Dyson web services."""
    device = mock.Mock()
    load_mock_device(device)
    device.connect = mock.Mock(return_value=False)
    device.auto_connect = mock.Mock(return_value=False)
    return device


def _get_dyson_account_device_error():
    """Return an invalid device raising OSError while connecting."""
    device = mock.Mock()
    load_mock_device(device)
    device.connect = mock.Mock(side_effect=OSError("Network error"))
    return device


class DysonTest(unittest.TestCase):
    """Dyson parent component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch("libpurecool.dyson.DysonAccount.login", return_value=False)
    def test_dyson_login_failed(self, mocked_login):
        """Test if Dyson connection failed."""
        dyson.setup(
            self.hass,
            {
                dyson.DOMAIN: {
                    dyson.CONF_USERNAME: "email",
                    dyson.CONF_PASSWORD: "password",
                    dyson.CONF_LANGUAGE: "FR",
                }
            },
        )
        assert mocked_login.call_count == 1

    @mock.patch("libpurecool.dyson.DysonAccount.devices", return_value=[])
    @mock.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
    def test_dyson_login(self, mocked_login, mocked_devices):
        """Test valid connection to dyson web service."""
        dyson.setup(
            self.hass,
            {
                dyson.DOMAIN: {
                    dyson.CONF_USERNAME: "email",
                    dyson.CONF_PASSWORD: "password",
                    dyson.CONF_LANGUAGE: "FR",
                }
            },
        )
        assert mocked_login.call_count == 1
        assert mocked_devices.call_count == 1
        assert len(self.hass.data[dyson.DYSON_DEVICES]) == 0

    @mock.patch("homeassistant.helpers.discovery.load_platform")
    @mock.patch(
        "libpurecool.dyson.DysonAccount.devices",
        return_value=[_get_dyson_account_device_available()],
    )
    @mock.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
    def test_dyson_custom_conf(self, mocked_login, mocked_devices, mocked_discovery):
        """Test device connection using custom configuration."""
        dyson.setup(
            self.hass,
            {
                dyson.DOMAIN: {
                    dyson.CONF_USERNAME: "email",
                    dyson.CONF_PASSWORD: "password",
                    dyson.CONF_LANGUAGE: "FR",
                    dyson.CONF_DEVICES: [
                        {"device_id": "XX-XXXXX-XX", "device_ip": "192.168.0.1"}
                    ],
                }
            },
        )
        assert mocked_login.call_count == 1
        assert mocked_devices.call_count == 1
        assert len(self.hass.data[dyson.DYSON_DEVICES]) == 1
        assert mocked_discovery.call_count == 5

    @mock.patch(
        "libpurecool.dyson.DysonAccount.devices",
        return_value=[_get_dyson_account_device_not_available()],
    )
    @mock.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
    def test_dyson_custom_conf_device_not_available(self, mocked_login, mocked_devices):
        """Test device connection with an invalid device."""
        dyson.setup(
            self.hass,
            {
                dyson.DOMAIN: {
                    dyson.CONF_USERNAME: "email",
                    dyson.CONF_PASSWORD: "password",
                    dyson.CONF_LANGUAGE: "FR",
                    dyson.CONF_DEVICES: [
                        {"device_id": "XX-XXXXX-XX", "device_ip": "192.168.0.1"}
                    ],
                }
            },
        )
        assert mocked_login.call_count == 1
        assert mocked_devices.call_count == 1
        assert len(self.hass.data[dyson.DYSON_DEVICES]) == 0

    @mock.patch(
        "libpurecool.dyson.DysonAccount.devices",
        return_value=[_get_dyson_account_device_error()],
    )
    @mock.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
    def test_dyson_custom_conf_device_error(self, mocked_login, mocked_devices):
        """Test device connection with device raising an exception."""
        dyson.setup(
            self.hass,
            {
                dyson.DOMAIN: {
                    dyson.CONF_USERNAME: "email",
                    dyson.CONF_PASSWORD: "password",
                    dyson.CONF_LANGUAGE: "FR",
                    dyson.CONF_DEVICES: [
                        {"device_id": "XX-XXXXX-XX", "device_ip": "192.168.0.1"}
                    ],
                }
            },
        )
        assert mocked_login.call_count == 1
        assert mocked_devices.call_count == 1
        assert len(self.hass.data[dyson.DYSON_DEVICES]) == 0

    @mock.patch("homeassistant.helpers.discovery.load_platform")
    @mock.patch(
        "libpurecool.dyson.DysonAccount.devices",
        return_value=[_get_dyson_account_device_available()],
    )
    @mock.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
    def test_dyson_custom_conf_with_unknown_device(
        self, mocked_login, mocked_devices, mocked_discovery
    ):
        """Test device connection with custom conf and unknown device."""
        dyson.setup(
            self.hass,
            {
                dyson.DOMAIN: {
                    dyson.CONF_USERNAME: "email",
                    dyson.CONF_PASSWORD: "password",
                    dyson.CONF_LANGUAGE: "FR",
                    dyson.CONF_DEVICES: [
                        {"device_id": "XX-XXXXX-XY", "device_ip": "192.168.0.1"}
                    ],
                }
            },
        )
        assert mocked_login.call_count == 1
        assert mocked_devices.call_count == 1
        assert len(self.hass.data[dyson.DYSON_DEVICES]) == 0
        assert mocked_discovery.call_count == 0

    @mock.patch("homeassistant.helpers.discovery.load_platform")
    @mock.patch(
        "libpurecool.dyson.DysonAccount.devices",
        return_value=[_get_dyson_account_device_available()],
    )
    @mock.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
    def test_dyson_discovery(self, mocked_login, mocked_devices, mocked_discovery):
        """Test device connection using discovery."""
        dyson.setup(
            self.hass,
            {
                dyson.DOMAIN: {
                    dyson.CONF_USERNAME: "email",
                    dyson.CONF_PASSWORD: "password",
                    dyson.CONF_LANGUAGE: "FR",
                    dyson.CONF_TIMEOUT: 5,
                    dyson.CONF_RETRY: 2,
                }
            },
        )
        assert mocked_login.call_count == 1
        assert mocked_devices.call_count == 1
        assert len(self.hass.data[dyson.DYSON_DEVICES]) == 1
        assert mocked_discovery.call_count == 5

    @mock.patch(
        "libpurecool.dyson.DysonAccount.devices",
        return_value=[_get_dyson_account_device_not_available()],
    )
    @mock.patch("libpurecool.dyson.DysonAccount.login", return_value=True)
    def test_dyson_discovery_device_not_available(self, mocked_login, mocked_devices):
        """Test device connection with discovery and invalid device."""
        dyson.setup(
            self.hass,
            {
                dyson.DOMAIN: {
                    dyson.CONF_USERNAME: "email",
                    dyson.CONF_PASSWORD: "password",
                    dyson.CONF_LANGUAGE: "FR",
                    dyson.CONF_TIMEOUT: 5,
                    dyson.CONF_RETRY: 2,
                }
            },
        )
        assert mocked_login.call_count == 1
        assert mocked_devices.call_count == 1
        assert len(self.hass.data[dyson.DYSON_DEVICES]) == 0
