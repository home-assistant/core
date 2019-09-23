"""The tests for the UniFi device tracker platform."""
from collections import deque
from copy import copy
from unittest.mock import Mock
from datetime import timedelta

import pytest

from aiounifi.clients import Clients, ClientsAll
from aiounifi.devices import Devices

from homeassistant import config_entries
from homeassistant.components import unifi
from homeassistant.components.unifi.const import (
    CONF_CONTROLLER,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    CONTROLLER_ID as CONF_CONTROLLER_ID,
    UNIFI_CONFIG,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

import homeassistant.components.device_tracker as device_tracker
import homeassistant.util.dt as dt_util

DEFAULT_DETECTION_TIME = timedelta(seconds=300)

CLIENT_1 = {
    "essid": "ssid",
    "hostname": "client_1",
    "ip": "10.0.0.1",
    "is_wired": False,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:01",
}
CLIENT_2 = {
    "hostname": "client_2",
    "ip": "10.0.0.2",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:02",
    "name": "Wired Client",
}
CLIENT_3 = {
    "essid": "ssid2",
    "hostname": "client_3",
    "ip": "10.0.0.3",
    "is_wired": False,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:03",
}

DEVICE_1 = {
    "board_rev": 3,
    "device_id": "mock-id",
    "has_fan": True,
    "fan_level": 0,
    "ip": "10.0.1.1",
    "last_seen": 1562600145,
    "mac": "00:00:00:00:01:01",
    "model": "US16P150",
    "name": "device_1",
    "overheating": True,
    "state": 1,
    "type": "usw",
    "upgradable": True,
    "version": "4.0.42.10433",
}
DEVICE_2 = {
    "board_rev": 3,
    "device_id": "mock-id",
    "has_fan": True,
    "ip": "10.0.1.1",
    "mac": "00:00:00:00:01:01",
    "model": "US16P150",
    "name": "device_1",
    "state": 0,
    "type": "usw",
    "version": "4.0.42.10433",
}

CONTROLLER_DATA = {
    CONF_HOST: "mock-host",
    CONF_USERNAME: "mock-user",
    CONF_PASSWORD: "mock-pswd",
    CONF_PORT: 1234,
    CONF_SITE_ID: "mock-site",
    CONF_VERIFY_SSL: True,
}

ENTRY_CONFIG = {CONF_CONTROLLER: CONTROLLER_DATA}

CONTROLLER_ID = CONF_CONTROLLER_ID.format(host="mock-host", site="mock-site")


@pytest.fixture
def mock_controller(hass):
    """Mock a UniFi Controller."""
    hass.data[UNIFI_CONFIG] = {}
    controller = unifi.UniFiController(hass, None)

    controller.api = Mock()
    controller.mock_requests = []

    controller.mock_client_responses = deque()
    controller.mock_device_responses = deque()
    controller.mock_client_all_responses = deque()

    async def mock_request(method, path, **kwargs):
        kwargs["method"] = method
        kwargs["path"] = path
        controller.mock_requests.append(kwargs)
        if path == "s/{site}/stat/sta":
            return controller.mock_client_responses.popleft()
        if path == "s/{site}/stat/device":
            return controller.mock_device_responses.popleft()
        if path == "s/{site}/rest/user":
            return controller.mock_client_all_responses.popleft()
        return None

    controller.api.clients = Clients({}, mock_request)
    controller.api.devices = Devices({}, mock_request)
    controller.api.clients_all = ClientsAll({}, mock_request)

    return controller


async def setup_controller(hass, mock_controller, options={}):
    """Load the UniFi switch platform with the provided controller."""
    hass.config.components.add(unifi.DOMAIN)
    hass.data[unifi.DOMAIN] = {CONTROLLER_ID: mock_controller}
    config_entry = config_entries.ConfigEntry(
        1,
        unifi.DOMAIN,
        "Mock Title",
        ENTRY_CONFIG,
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        entry_id=1,
        system_options={},
        options=options,
    )
    hass.config_entries._entries.append(config_entry)
    mock_controller.config_entry = config_entry

    await mock_controller.async_update()
    await hass.config_entries.async_forward_entry_setup(
        config_entry, device_tracker.DOMAIN
    )

    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a bridge."""
    assert (
        await async_setup_component(
            hass, device_tracker.DOMAIN, {device_tracker.DOMAIN: {"platform": "unifi"}}
        )
        is True
    )
    assert unifi.DOMAIN not in hass.data


async def test_no_clients(hass, mock_controller):
    """Test the update_clients function when no clients are found."""
    mock_controller.mock_client_responses.append({})
    mock_controller.mock_device_responses.append({})

    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    assert len(hass.states.async_all()) == 2


async def test_tracked_devices(hass, mock_controller):
    """Test the update_items function with some clients."""
    mock_controller.mock_client_responses.append([CLIENT_1, CLIENT_2, CLIENT_3])
    mock_controller.mock_device_responses.append([DEVICE_1, DEVICE_2])
    options = {CONF_SSID_FILTER: ["ssid"]}

    await setup_controller(hass, mock_controller, options)
    assert len(mock_controller.mock_requests) == 2
    assert len(hass.states.async_all()) == 5

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "not_home"

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None
    assert client_2.state == "not_home"

    client_3 = hass.states.get("device_tracker.client_3")
    assert client_3 is None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "not_home"

    client_1_copy = copy(CLIENT_1)
    client_1_copy["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())
    device_1_copy = copy(DEVICE_1)
    device_1_copy["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())
    mock_controller.mock_client_responses.append([client_1_copy])
    mock_controller.mock_device_responses.append([device_1_copy])
    await mock_controller.async_update()
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == "home"

    device_1_copy = copy(DEVICE_1)
    device_1_copy["disabled"] = True
    mock_controller.mock_client_responses.append({})
    mock_controller.mock_device_responses.append([device_1_copy])
    await mock_controller.async_update()
    await hass.async_block_till_done()

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == STATE_UNAVAILABLE

    mock_controller.config_entry.add_update_listener(
        mock_controller.async_options_updated
    )
    hass.config_entries.async_update_entry(
        mock_controller.config_entry,
        options={
            CONF_SSID_FILTER: [],
            CONF_TRACK_WIRED_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        },
    )
    await hass.async_block_till_done()
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1
    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is None
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is None


async def test_restoring_client(hass, mock_controller):
    """Test the update_items function with some clients."""
    mock_controller.mock_client_responses.append([CLIENT_2])
    mock_controller.mock_device_responses.append({})
    mock_controller.mock_client_all_responses.append([CLIENT_1])
    options = {unifi.CONF_BLOCK_CLIENT: True}

    config_entry = config_entries.ConfigEntry(
        1,
        unifi.DOMAIN,
        "Mock Title",
        ENTRY_CONFIG,
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        entry_id=1,
        system_options={},
    )

    registry = await entity_registry.async_get_registry(hass)
    registry.async_get_or_create(
        device_tracker.DOMAIN,
        unifi.DOMAIN,
        "{}-mock-site".format(CLIENT_1["mac"]),
        suggested_object_id=CLIENT_1["hostname"],
        config_entry=config_entry,
    )
    registry.async_get_or_create(
        device_tracker.DOMAIN,
        unifi.DOMAIN,
        "{}-mock-site".format(CLIENT_2["mac"]),
        suggested_object_id=CLIENT_2["hostname"],
        config_entry=config_entry,
    )

    await setup_controller(hass, mock_controller, options)
    assert len(mock_controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 4

    device_1 = hass.states.get("device_tracker.client_1")
    assert device_1 is not None


async def test_dont_track_clients(hass, mock_controller):
    """Test dont track clients config works."""
    mock_controller.mock_client_responses.append([CLIENT_1])
    mock_controller.mock_device_responses.append([DEVICE_1])
    options = {unifi.controller.CONF_TRACK_CLIENTS: False}

    await setup_controller(hass, mock_controller, options)
    assert len(mock_controller.mock_requests) == 2
    assert len(hass.states.async_all()) == 3

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "not_home"


async def test_dont_track_devices(hass, mock_controller):
    """Test dont track devices config works."""
    mock_controller.mock_client_responses.append([CLIENT_1])
    mock_controller.mock_device_responses.append([DEVICE_1])
    options = {unifi.controller.CONF_TRACK_DEVICES: False}

    await setup_controller(hass, mock_controller, options)
    assert len(mock_controller.mock_requests) == 2
    assert len(hass.states.async_all()) == 3

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "not_home"

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is None


async def test_dont_track_wired_clients(hass, mock_controller):
    """Test dont track wired clients config works."""
    mock_controller.mock_client_responses.append([CLIENT_1, CLIENT_2])
    mock_controller.mock_device_responses.append({})
    options = {unifi.controller.CONF_TRACK_WIRED_CLIENTS: False}

    await setup_controller(hass, mock_controller, options)
    assert len(mock_controller.mock_requests) == 2
    assert len(hass.states.async_all()) == 3

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "not_home"

    client_2 = hass.states.get("device_tracker.client_2")
    assert client_2 is None
