"""The tests for the tplink device tracker platform."""

import os

import pytest
import requests_mock

from homeassistant.components import device_tracker
from homeassistant.components.tplink.device_tracker import Tplink4DeviceScanner
from homeassistant.const import (CONF_PLATFORM, CONF_PASSWORD, CONF_USERNAME,
                                 CONF_HOST)


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    yaml_devices = hass.config.path(device_tracker.YAML_DEVICES)
    yield
    if os.path.isfile(yaml_devices):
        os.remove(yaml_devices)


async def test_get_mac_addresses_from_both_bands(hass):
    """Test grabbing the mac addresses from 2.4 and 5 GHz clients pages."""
    with requests_mock.Mocker() as req_mock:
        conf_dict = {
            CONF_PLATFORM: 'tplink',
            CONF_HOST: 'fake-host',
            CONF_USERNAME: 'fake_user',
            CONF_PASSWORD: 'fake_pass'
        }

        # Mock the token retrieval process
        fake_token = 'fake_token'
        fake_auth_token_response = 'window.parent.location.href = ' \
            '"https://a/{}/userRpm/Index.htm";'.format(fake_token)

        req_mock.get('http://{}/userRpm/LoginRpm.htm?Save=Save'.format(
            conf_dict[CONF_HOST]), text=fake_auth_token_response)

        fake_mac_1 = 'CA-FC-8A-C8-BB-53'
        fake_mac_2 = '6C-48-83-21-46-8D'
        fake_mac_3 = '77-98-75-65-B1-2B'
        mac_response_2_4 = '{} {}'.format(fake_mac_1, fake_mac_2)
        mac_response_5 = '{}'.format(fake_mac_3)

        # Mock the 2.4 GHz clients page
        req_mock.get('http://{}/{}/userRpm/WlanStationRpm.htm'.format(
            conf_dict[CONF_HOST], fake_token), text=mac_response_2_4)

        # Mock the 5 GHz clients page
        req_mock.get('http://{}/{}/userRpm/WlanStationRpm_5g.htm'.format(
            conf_dict[CONF_HOST], fake_token), text=mac_response_5)

        tplink = Tplink4DeviceScanner(conf_dict)

        expected_mac_results = [mac.replace('-', ':') for mac in
                                [fake_mac_1, fake_mac_2, fake_mac_3]]

        assert tplink.last_results == expected_mac_results
