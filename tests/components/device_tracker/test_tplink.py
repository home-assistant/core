"""The tests for the tplink device tracker platform."""

import os
import pytest

from homeassistant.components import device_tracker
from homeassistant.components.device_tracker.tplink import Tplink4DeviceScanner
from homeassistant.const import (CONF_PLATFORM, CONF_PASSWORD, CONF_USERNAME,
                                 CONF_HOST)
import requests_mock


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    yaml_devices = hass.config.path(device_tracker.YAML_DEVICES)
    yield
    if os.path.isfile(yaml_devices):
        os.remove(yaml_devices)


async def test_get_mac_addresses_from_both_bands(hass):
    """Test grabbing the mac addresses from 2.4 and 5 GHz clients pages."""
    with requests_mock.Mocker() as m:
        conf_dict = {
            CONF_PLATFORM: 'tplink',
            CONF_HOST: 'fake-host',
            CONF_USERNAME: 'fake_user',
            CONF_PASSWORD: 'fake_pass'
        }

        # Mock the token retrieval process
        FAKE_TOKEN = 'fake_token'
        fake_auth_token_response = 'window.parent.location.href = ' \
            '"https://a/{}/userRpm/Index.htm";'.format(FAKE_TOKEN)

        m.get('http://{}/userRpm/LoginRpm.htm?Save=Save'.format(
            conf_dict[CONF_HOST]), text=fake_auth_token_response)

        FAKE_MAC_1 = 'CA-FC-8A-C8-BB-53'
        FAKE_MAC_2 = '6C-48-83-21-46-8D'
        FAKE_MAC_3 = '77-98-75-65-B1-2B'
        mac_response_2_4 = '{} {}'.format(FAKE_MAC_1, FAKE_MAC_2)
        mac_response_5 = '{}'.format(FAKE_MAC_3)

        # Mock the 2.4 GHz clients page
        m.get('http://{}/{}/userRpm/WlanStationRpm.htm'.format(
            conf_dict[CONF_HOST], FAKE_TOKEN), text=mac_response_2_4)

        # Mock the 5 GHz clients page
        m.get('http://{}/{}/userRpm/WlanStationRpm_5g.htm'.format(
            conf_dict[CONF_HOST], FAKE_TOKEN), text=mac_response_5)

        tplink = Tplink4DeviceScanner(conf_dict)

        expected_mac_results = [mac.replace('-', ':') for mac in
                                [FAKE_MAC_1, FAKE_MAC_2, FAKE_MAC_3]]

        assert tplink.last_results == expected_mac_results
