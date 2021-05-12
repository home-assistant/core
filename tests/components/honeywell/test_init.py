"""The test the Honeywell service module."""
import unittest
from unittest import mock

import somecomfort

from homeassistant.components import honeywell
from homeassistant.components.honeywell.const import CONF_DEV_ID, CONF_LOC_ID
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME


class TestHoneywell(unittest.TestCase):
    """A test class for Honeywell Devices."""

    @mock.patch("somecomfort.SomeComfort")
    def test_setup_failures(self, mock_sc):
        """Test the US setup."""
        hass = mock.MagicMock()
        config = {
            honeywell.DOMAIN: {
                CONF_USERNAME: None,
                CONF_PASSWORD: None,
                CONF_LOC_ID: None,
                CONF_DEV_ID: None,
            },
        }

        mock_sc.side_effect = somecomfort.AuthError
        result = honeywell.setup(
            hass,
            config,
        )
        assert not result

        mock_sc.side_effect = somecomfort.SomeComfortError
        honeywell.setup(hass, config)
        assert not result
