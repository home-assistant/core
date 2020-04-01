"""Test UniFi Controller."""
from collections import deque
from copy import deepcopy
from datetime import timedelta

import aiounifi
from asynctest import Mock, patch
import pytest

from homeassistant.components import unifi
from homeassistant.components.unifi.const import (
    CONF_CONTROLLER,
    CONF_SITE_ID,
    UNIFI_WIRELESS_CLIENTS,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CONTROLLER_HOST = {
    "hostname": "controller_host",
    "ip": "1.2.3.4",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "10:00:00:00:00:01",
    "name": "Controller host",
    "oui": "Producer",
    "sw_mac": "00:00:00:00:01:01",
    "sw_port": 1,
    "wired-rx_bytes": 1234000000,
    "wired-tx_bytes": 5678000000,
}

CONTROLLER_DATA = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 1234,
    CONF_SITE_ID: "site_id",
    CONF_VERIFY_SSL: False,
}

ENTRY_CONFIG = {CONF_CONTROLLER: CONTROLLER_DATA}
ENTRY_OPTIONS = {}

CONFIGURATION = []

SITES = {"Site name": {"desc": "Site name", "name": "site_id", "role": "admin"}}


async def setup_unifi_integration(
    hass,
    config=ENTRY_CONFIG,
    options=ENTRY_OPTIONS,
    sites=SITES,
    clients_response=None,
    devices_response=None,
    clients_all_response=None,
    wlans_response=None,
    known_wireless_clients=None,
    controllers=None,
):
    """Create the UniFi controller."""
    configuration = {}
    if controllers:
        configuration = {unifi.DOMAIN: {unifi.CONF_CONTROLLERS: controllers}}

    assert await async_setup_component(hass, unifi.DOMAIN, configuration)

    config_entry = MockConfigEntry(
        domain=unifi.DOMAIN,
        data=deepcopy(config),
        options=deepcopy(options),
        entry_id=1,
    )
    config_entry.add_to_hass(hass)

    if known_wireless_clients:
        hass.data[UNIFI_WIRELESS_CLIENTS].update_data(
            known_wireless_clients, config_entry
        )

    mock_client_responses = deque()
    if clients_response:
        mock_client_responses.append(clients_response)

    mock_device_responses = deque()
    if devices_response:
        mock_device_responses.append(devices_response)

    mock_client_all_responses = deque()
    if clients_all_response:
        mock_client_all_responses.append(clients_all_response)

    mock_wlans_responses = deque()
    if wlans_response:
        mock_wlans_responses.append(wlans_response)

    mock_requests = []

    async def mock_request(self, method, path, json=None):
        mock_requests.append({"method": method, "path": path, "json": json})

        if path == "s/{site}/stat/sta" and mock_client_responses:
            return mock_client_responses.popleft()
        if path == "s/{site}/stat/device" and mock_device_responses:
            return mock_device_responses.popleft()
        if path == "s/{site}/rest/user" and mock_client_all_responses:
            return mock_client_all_responses.popleft()
        if path == "s/{site}/rest/wlanconf" and mock_wlans_responses:
            return mock_wlans_responses.popleft()
        return {}

    # "aiounifi.Controller.start_websocket", return_value=True
    with patch("aiounifi.Controller.login", return_value=True), patch(
        "aiounifi.Controller.sites", return_value=sites
    ), patch("aiounifi.Controller.request", new=mock_request), patch.object(
        aiounifi.websocket.WSClient, "start", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    controller_id = unifi.get_controller_id_from_config_entry(config_entry)
    if controller_id not in hass.data[unifi.DOMAIN]:
        return None
    controller = hass.data[unifi.DOMAIN][controller_id]

    controller.mock_client_responses = mock_client_responses
    controller.mock_device_responses = mock_device_responses
    controller.mock_client_all_responses = mock_client_all_responses
    controller.mock_wlans_responses = mock_wlans_responses
    controller.mock_requests = mock_requests

    return controller


async def test_controller_setup(hass):
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        controller = await setup_unifi_integration(hass)

    entry = controller.config_entry
    assert len(forward_entry_setup.mock_calls) == len(
        unifi.controller.SUPPORTED_PLATFORMS
    )
    assert forward_entry_setup.mock_calls[0][1] == (entry, "device_tracker")
    assert forward_entry_setup.mock_calls[1][1] == (entry, "sensor")
    assert forward_entry_setup.mock_calls[2][1] == (entry, "switch")

    assert controller.host == CONTROLLER_DATA[CONF_HOST]
    assert controller.site == CONTROLLER_DATA[CONF_SITE_ID]
    assert controller.site_name in SITES
    assert controller.site_role == SITES[controller.site_name]["role"]

    assert (
        controller.option_allow_bandwidth_sensors
        == unifi.const.DEFAULT_ALLOW_BANDWIDTH_SENSORS
    )
    assert isinstance(controller.option_block_clients, list)
    assert controller.option_track_clients == unifi.const.DEFAULT_TRACK_CLIENTS
    assert controller.option_track_devices == unifi.const.DEFAULT_TRACK_DEVICES
    assert (
        controller.option_track_wired_clients == unifi.const.DEFAULT_TRACK_WIRED_CLIENTS
    )
    assert controller.option_detection_time == timedelta(
        seconds=unifi.const.DEFAULT_DETECTION_TIME
    )
    assert isinstance(controller.option_ssid_filter, list)

    assert controller.mac is None

    assert controller.signal_update == "unifi-update-1.2.3.4-site_id"
    assert controller.signal_options_update == "unifi-options-1.2.3.4-site_id"


async def test_controller_mac(hass):
    """Test that it is possible to identify controller mac."""
    controller = await setup_unifi_integration(hass, clients_response=[CONTROLLER_HOST])
    assert controller.mac == "10:00:00:00:00:01"


async def test_controller_not_accessible(hass):
    """Retry to login gets scheduled when connection fails."""
    with patch.object(
        unifi.controller, "get_controller", side_effect=unifi.errors.CannotConnect
    ):
        await setup_unifi_integration(hass)
    assert hass.data[unifi.DOMAIN] == {}


async def test_controller_unknown_error(hass):
    """Unknown errors are handled."""
    with patch.object(unifi.controller, "get_controller", side_effect=Exception):
        await setup_unifi_integration(hass)
    assert hass.data[unifi.DOMAIN] == {}


async def test_reset_after_successful_setup(hass):
    """Calling reset when the entry has been setup."""
    controller = await setup_unifi_integration(hass)

    assert len(controller.listeners) == 6

    result = await controller.async_reset()
    await hass.async_block_till_done()

    assert result is True
    assert len(controller.listeners) == 0


async def test_wireless_client_event_calls_update_wireless_devices(hass):
    """Call update_wireless_devices method when receiving wireless client event."""
    controller = await setup_unifi_integration(hass)

    with patch(
        "homeassistant.components.unifi.controller.UniFiController.update_wireless_clients",
        return_value=None,
    ) as wireless_clients_mock:
        controller.api.websocket._data = {
            "meta": {"rc": "ok", "message": "events"},
            "data": [
                {
                    "datetime": "2020-01-20T19:37:04Z",
                    "key": aiounifi.events.WIRELESS_CLIENT_CONNECTED,
                    "msg": "User[11:22:33:44:55:66] has connected to WLAN",
                    "time": 1579549024893,
                }
            ],
        }
        controller.api.session_handler("data")

        assert wireless_clients_mock.assert_called_once


async def test_get_controller(hass):
    """Successful call."""
    with patch("aiounifi.Controller.login", return_value=Mock()):
        assert await unifi.controller.get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_verify_ssl_false(hass):
    """Successful call with verify ssl set to false."""
    controller_data = dict(CONTROLLER_DATA)
    controller_data[CONF_VERIFY_SSL] = False
    with patch("aiounifi.Controller.login", return_value=Mock()):
        assert await unifi.controller.get_controller(hass, **controller_data)


async def test_get_controller_login_failed(hass):
    """Check that get_controller can handle a failed login."""
    with patch(
        "aiounifi.Controller.login", side_effect=aiounifi.Unauthorized
    ), pytest.raises(unifi.errors.AuthenticationRequired):
        await unifi.controller.get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_controller_unavailable(hass):
    """Check that get_controller can handle controller being unavailable."""
    with patch(
        "aiounifi.Controller.login", side_effect=aiounifi.RequestError
    ), pytest.raises(unifi.errors.CannotConnect):
        await unifi.controller.get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_unknown_error(hass):
    """Check that get_controller can handle unknown errors."""
    with patch(
        "aiounifi.Controller.login", side_effect=aiounifi.AiounifiException
    ), pytest.raises(unifi.errors.AuthenticationRequired):
        await unifi.controller.get_controller(hass, **CONTROLLER_DATA)
