"""The tests for the BT Home Hub 5 device tracker platform."""
import unittest
from unittest.mock import patch

from homeassistant.components.device_tracker import bt_home_hub_5
from homeassistant.const import CONF_HOST

patch_file = 'homeassistant.components.device_tracker.bt_home_hub_5'


def _get_homehub_data(url):
    return '''
    [
        {
            "mac": "AA:BB:CC:DD:EE:FF,
            "hostname": "hostname",
            "ip": "192.168.1.43",
            "ipv6": "",
            "name": "hostname",
            "activity": "1",
            "os": "Unknown",
            "device": "Unknown",
            "time_first_seen": "2016/06/05 11:14:45",
            "time_last_active": "2016/06/06 11:33:08",
            "dhcp_option": "39043T90430T9TGK0EKGE5KGE3K904390K45GK054",
            "port": "wl0",
            "ipv6_ll": "fe80::gd67:ghrr:fuud:4332",
            "activity_ip": "1",
            "activity_ipv6_ll": "0",
            "activity_ipv6": "0",
            "device_oui": "NA",
            "device_serial": "NA",
            "device_class": "NA"
        }
    ]
    '''


class TestBTHomeHub5DeviceTracker(unittest.TestCase):
    """Test BT Home Hub 5 device tracker platform."""

    @patch('{}._get_homehub_data'.format(patch_file), new=_get_homehub_data)
    def test_config_minimal(self):
        """Test the setup with minimal configuration."""

        config = {
            'device_tracker': {
                CONF_HOST: 'foo'
            }
        }
        result = bt_home_hub_5.get_scanner(None, config)

        self.assertIsNotNone(result)
