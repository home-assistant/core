"""Test UniFi Controller."""
from collections import deque
from datetime import timedelta

import aiounifi
from asynctest import Mock, patch
import pytest

from homeassistant import config_entries
from homeassistant.components import unifi
from homeassistant.components.unifi.const import (
    CONF_CONTROLLER,
    CONF_SITE_ID,
    UNIFI_CONFIG,
    UNIFI_WIRELESS_CLIENTS,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import ConfigEntryNotReady

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

SITES = {"Site name": {"desc": "Site name", "name": "site_id", "role": "admin"}}


async def setup_unifi_integration(
    hass,
    config,
    options,
    sites,
    clients_response,
    devices_response,
    clients_all_response,
):
    """Create the UniFi controller."""
    if UNIFI_CONFIG not in hass.data:
        hass.data[UNIFI_CONFIG] = []
    hass.data[UNIFI_WIRELESS_CLIENTS] = unifi.UnifiWirelessClients(hass)
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=unifi.DOMAIN,
        title="Mock Title",
        data=config,
        source="test",
        connection_class=config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
        options=options,
        entry_id=1,
    )

    mock_client_responses = deque()
    mock_client_responses.append(clients_response)

    mock_device_responses = deque()
    mock_device_responses.append(devices_response)

    mock_client_all_responses = deque()
    mock_client_all_responses.append(clients_all_response)

    mock_requests = []

    async def mock_request(self, method, path, json=None):
        mock_requests.append({"method": method, "path": path, "json": json})

        if path == "s/{site}/stat/sta" and mock_client_responses:
            return mock_client_responses.popleft()
        if path == "s/{site}/stat/device" and mock_device_responses:
            return mock_device_responses.popleft()
        if path == "s/{site}/rest/user" and mock_client_all_responses:
            return mock_client_all_responses.popleft()
        return {}

    with patch("aiounifi.Controller.login", return_value=True), patch(
        "aiounifi.Controller.sites", return_value=sites
    ), patch("aiounifi.Controller.request", new=mock_request):
        await unifi.async_setup_entry(hass, config_entry)
    await hass.async_block_till_done()
    hass.config_entries._entries.append(config_entry)

    controller_id = unifi.get_controller_id_from_config_entry(config_entry)
    if controller_id not in hass.data[unifi.DOMAIN]:
        return None
    controller = hass.data[unifi.DOMAIN][controller_id]

    controller.mock_client_responses = mock_client_responses
    controller.mock_device_responses = mock_device_responses
    controller.mock_client_all_responses = mock_client_all_responses
    controller.mock_requests = mock_requests

    return controller


async def test_controller_setup(hass):
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        controller = await setup_unifi_integration(
            hass,
            ENTRY_CONFIG,
            options={},
            sites=SITES,
            clients_response=[],
            devices_response=[],
            clients_all_response=[],
        )

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
    assert controller.option_block_clients == unifi.const.DEFAULT_BLOCK_CLIENTS
    assert controller.option_track_clients == unifi.const.DEFAULT_TRACK_CLIENTS
    assert controller.option_track_devices == unifi.const.DEFAULT_TRACK_DEVICES
    assert (
        controller.option_track_wired_clients == unifi.const.DEFAULT_TRACK_WIRED_CLIENTS
    )
    assert controller.option_detection_time == timedelta(
        seconds=unifi.const.DEFAULT_DETECTION_TIME
    )
    assert controller.option_ssid_filter == unifi.const.DEFAULT_SSID_FILTER

    assert controller.mac is None

    assert controller.signal_update == "unifi-update-1.2.3.4-site_id"
    assert controller.signal_options_update == "unifi-options-1.2.3.4-site_id"


async def test_controller_mac(hass):
    """Test that it is possible to identify controller mac."""
    controller = await setup_unifi_integration(
        hass,
        ENTRY_CONFIG,
        options={},
        sites=SITES,
        clients_response=[CONTROLLER_HOST],
        devices_response=[],
        clients_all_response=[],
    )
    assert controller.mac == "10:00:00:00:00:01"


async def test_controller_import_config(hass):
    """Test that import configuration.yaml instructions work."""
    hass.data[UNIFI_CONFIG] = [
        {
            CONF_HOST: "1.2.3.4",
            CONF_SITE_ID: "Site name",
            unifi.const.CONF_ALLOW_BANDWIDTH_SENSORS: True,
            unifi.CONF_BLOCK_CLIENT: ["random mac"],
            unifi.CONF_DONT_TRACK_CLIENTS: True,
            unifi.CONF_DONT_TRACK_DEVICES: True,
            unifi.CONF_DONT_TRACK_WIRED_CLIENTS: True,
            unifi.CONF_DETECTION_TIME: 150,
            unifi.CONF_SSID_FILTER: ["SSID"],
        }
    ]
    controller = await setup_unifi_integration(
        hass,
        ENTRY_CONFIG,
        options={},
        sites=SITES,
        clients_response=[],
        devices_response=[],
        clients_all_response=[],
    )

    assert controller.option_allow_bandwidth_sensors is False
    assert controller.option_block_clients == ["random mac"]
    assert controller.option_track_clients is False
    assert controller.option_track_devices is False
    assert controller.option_track_wired_clients is False
    assert controller.option_detection_time == timedelta(seconds=150)
    assert controller.option_ssid_filter == ["SSID"]


async def test_controller_not_accessible(hass):
    """Retry to login gets scheduled when connection fails."""
    with patch.object(
        unifi.controller, "get_controller", side_effect=unifi.errors.CannotConnect
    ), pytest.raises(ConfigEntryNotReady):
        await setup_unifi_integration(
            hass,
            ENTRY_CONFIG,
            options={},
            sites=SITES,
            clients_response=[],
            devices_response=[],
            clients_all_response=[],
        )


async def test_controller_unknown_error(hass):
    """Unknown errors are handled."""
    with patch.object(unifi.controller, "get_controller", side_effect=Exception):
        await setup_unifi_integration(
            hass,
            ENTRY_CONFIG,
            options={},
            sites=SITES,
            clients_response=[],
            devices_response=[],
            clients_all_response=[],
        )
        assert hass.data[unifi.DOMAIN] == {}


async def test_reset_after_successful_setup(hass):
    """Calling reset when the entry has been setup."""
    controller = await setup_unifi_integration(
        hass,
        ENTRY_CONFIG,
        options={},
        sites=SITES,
        clients_response=[],
        devices_response=[],
        clients_all_response=[],
    )

    assert len(controller.listeners) == 5

    result = await controller.async_reset()
    await hass.async_block_till_done()

    assert result is True
    assert len(controller.listeners) == 0


async def test_failed_update_failed_login(hass):
    """Running update can handle a failed login."""
    controller = await setup_unifi_integration(
        hass,
        ENTRY_CONFIG,
        options={},
        sites=SITES,
        clients_response=[],
        devices_response=[],
        clients_all_response=[],
    )

    with patch.object(
        controller.api.clients, "update", side_effect=aiounifi.LoginRequired
    ), patch.object(controller.api, "login", side_effect=aiounifi.AiounifiException):
        await controller.async_update()
    await hass.async_block_till_done()

    assert controller.available is False


async def test_failed_update_successful_login(hass):
    """Running update can login when requested."""
    controller = await setup_unifi_integration(
        hass,
        ENTRY_CONFIG,
        options={},
        sites=SITES,
        clients_response=[],
        devices_response=[],
        clients_all_response=[],
    )

    with patch.object(
        controller.api.clients, "update", side_effect=aiounifi.LoginRequired
    ), patch.object(controller.api, "login", return_value=Mock(True)):
        await controller.async_update()
    await hass.async_block_till_done()

    assert controller.available is True


async def test_failed_update(hass):
    """Running update can login when requested."""
    controller = await setup_unifi_integration(
        hass,
        ENTRY_CONFIG,
        options={},
        sites=SITES,
        clients_response=[],
        devices_response=[],
        clients_all_response=[],
    )

    with patch.object(
        controller.api.clients, "update", side_effect=aiounifi.AiounifiException
    ):
        await controller.async_update()
    await hass.async_block_till_done()

    assert controller.available is False

    await controller.async_update()
    await hass.async_block_till_done()
    assert controller.available is True


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
    result = None
    with patch("aiounifi.Controller.login", side_effect=aiounifi.Unauthorized):
        try:
            result = await unifi.controller.get_controller(hass, **CONTROLLER_DATA)
        except unifi.errors.AuthenticationRequired:
            pass
        assert result is None


async def test_get_controller_controller_unavailable(hass):
    """Check that get_controller can handle controller being unavailable."""
    result = None
    with patch("aiounifi.Controller.login", side_effect=aiounifi.RequestError):
        try:
            result = await unifi.controller.get_controller(hass, **CONTROLLER_DATA)
        except unifi.errors.CannotConnect:
            pass
        assert result is None


async def test_get_controller_unknown_error(hass):
    """Check that get_controller can handle unkown errors."""
    result = None
    with patch("aiounifi.Controller.login", side_effect=aiounifi.AiounifiException):
        try:
            result = await unifi.controller.get_controller(hass, **CONTROLLER_DATA)
        except unifi.errors.AuthenticationRequired:
            pass
        assert result is None
