"""
Support for BT Home Hub 5.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bt_home_hub_5/
"""
import logging
import re
import xml.etree.ElementTree as ET
import json
from hashlib import md5
from urllib.parse import unquote

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD

REQUIREMENTS = ['beautifulsoup4==4.6.0']

_LOGGER = logging.getLogger(__name__)
_MAC_REGEX = re.compile(r'([0-9a-f]{2}\:){5}[0-9a-f]{2}')
_HOMEPAGE = '?active_page=9098'  # router homepage: has device list, no login
_AUTHPAGE = '?active_page=9100'  # any page that prompts for login
_DHCPPAGE = '?active_page=9140'  # page containing DHCP table

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default='192.168.1.254'): cv.string,
    vol.Optional(CONF_PASSWORD, default=None): cv.string,
})


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """Return a BT Home Hub 5 scanner if successful."""
    scanner = BTHomeHub5DeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class BTHomeHub5DeviceScanner(DeviceScanner):
    """This class queries a BT Home Hub 5."""

    def __init__(self, config):
        """Initialise the scanner."""
        _LOGGER.info("Initialising BT Home Hub 5")
        self.baseurl = 'http://{}/index.cgi'.format(config[CONF_HOST])
        self.password = config[CONF_PASSWORD]
        self.last_results = {}

        # Test the router is accessible
        data = _get_homehub_data(self.baseurl, self.password)
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return (device for device in self.last_results)

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # If not initialised and not already scanned and not found.
        if device not in self.last_results:
            self._update_info()

            if not self.last_results:
                return None

        return self.last_results.get(device)

    def _update_info(self):
        """Ensure the information from the BT Home Hub 5 is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Scanning")

        data = _get_homehub_data(self.baseurl, self.password)

        if not data:
            _LOGGER.warning("Error scanning devices")
            return False

        self.last_results = data

        return True


def _get_homehub_data(baseurl, password=None):
    """Retrieve data from BT Home Hub 5 and return parsed result."""
    if password is not None:
        cookiedict = _auth_homehub(baseurl, password)
        if cookiedict is None:
            _LOGGER.error("Failed to retrieve cookie for BT Home Hub")
            return
        response = _try_request('GET', '{}{}'.format(baseurl, _DHCPPAGE),
                                cookies=cookiedict)
        if response is None:
            return
    else:
        # Fall back to non-authenticating method, may truncate device names
        response = _try_request('GET', '{}{}'.format(baseurl, _HOMEPAGE))
        if response is None:
            return
    return _parse_homehub_device_table_from_html(response.text)


def _auth_homehub(baseurl, password):
    """Get an authenticated cookie from the homehub."""
    from bs4 import BeautifulSoup

    # Extract the required params for authenticating the cookie
    response = _try_request('GET', '{}{}'.format(baseurl, _AUTHPAGE))
    if response is None:
        return
    cookie_name = 'rg_cookie_session_id'
    cookiedict = {cookie_name: response.cookies[cookie_name]}
    soup = BeautifulSoup(response.text, 'html.parser')
    request_id = soup.find(attrs={'name': 'request_id'}).attrs['value']
    post_token = soup.find(attrs={'name': 'post_token'}).attrs['value']
    auth_key = soup.find(attrs={'name': 'auth_key'}).attrs['value']
    password_field = soup.find(id='password').attrs['name']
    # Probably not actually utf-8, but default passwords are ascii anyway
    md5_pass = md5((password + auth_key).encode('utf-8')).hexdigest()

    # Perform authenticating request, mimicking browser as much as reasonable
    response = _try_request('POST', baseurl, cookies=cookiedict, data={
        'request_id': request_id,
        'active_page': '9148',
        'active_page_str': 'bt_login',
        'mimic_button_field': 'submit_button_login_submit: ..',
        'button_value': '',
        'post_token': post_token,
        password_field: '',
        'md5_pass': md5_pass,
        'auth_key': auth_key,
    })
    if response is None or 'BT Home Hub Manager - Login' in response.text:
        return
    return cookiedict


def _try_request(method, url, **kwargs):
    """Send request to BT Home Hub 5."""
    try:
        response = requests.request(method, url, timeout=8, **kwargs)
    except requests.exceptions.Timeout:
        _LOGGER.exception("Connection to the router timed out")
        return
    if response.status_code == 200:
        return response
    else:
        _LOGGER.error("Invalid response from Home Hub when %s %s: %s",
                      method, url, response)


def _parse_homehub_device_table_from_html(data_str):
    """Find and parse a table of devices from the BT Home Hub 5.

    The homepage and DHCP table page tables are similar enough that we can
    use common code.
    """
    from bs4 import BeautifulSoup

    # Find the beginning of devices table (the header)
    soup = BeautifulSoup(data_str, 'html.parser')
    macaddr_header = soup.find(text='MAC Address')
    if macaddr_header is None:
        _LOGGER.error("Could not find 'MAC Address' header")
        return
    table_header_row = macaddr_header.parent.parent  # -> th -> tr
    if table_header_row.name != 'tr':
        _LOGGER.error("Header row not in the expected place")
        return

    # Identify columns of mac addr and device name. Device name is sadly
    # truncated, but the untuncated one requires authentication to get to.
    mac_address_col = None
    device_name_col = None
    for i, headercell in enumerate(table_header_row.children):
        if headercell.find(text='MAC Address'):
            mac_address_col = i
        elif headercell.find(text='Device'):
            device_name_col = i
    if device_name_col is None or mac_address_col is None:
        _LOGGER.error("Couldn't find columns of mac address and device name")
        return

    # Run through all the rows of the table, hunting for anything with a MAC.
    # Rows of device tables seem to have alternating bgcolor, so repeat until
    # we run out of them.
    devices = {}
    tablerow = table_header_row
    while (tablerow.next_sibling is not None and
            'bgcolor' in tablerow.next_sibling.attrs):
        tablerow = tablerow.next_sibling
        cells = list(tablerow.children)
        mac_address = cells[mac_address_col].text
        device_name = cells[device_name_col].text
        if _MAC_REGEX.match(mac_address):
            devices[mac_address] = device_name

    return devices
