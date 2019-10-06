"""UniFi sensor platform tests."""
from collections import deque
from copy import deepcopy

from asynctest import patch

from homeassistant import config_entries
from homeassistant.components import unifi
from homeassistant.components.unifi.const import (
    CONF_CONTROLLER,
    CONF_SITE_ID,
    CONTROLLER_ID as CONF_CONTROLLER_ID,
    UNIFI_CONFIG,
    UNIFI_WIRELESS_CLIENTS,
)
from homeassistant.setup import async_setup_component
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

import homeassistant.components.sensor as sensor

CLIENTS = [
    {
        "hostname": "Wired client hostname",
        "ip": "10.0.0.1",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
        "name": "Wired client name",
        "oui": "Producer",
        "sw_mac": "00:00:00:00:01:01",
        "sw_port": 1,
        "wired-rx_bytes": 1234000000,
        "wired-tx_bytes": 5678000000,
    },
    {
        "hostname": "Wireless client hostname",
        "ip": "10.0.0.2",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
        "name": "Wireless client name",
        "oui": "Producer",
        "sw_mac": "00:00:00:00:01:01",
        "sw_port": 2,
        "rx_bytes": 1234000000,
        "tx_bytes": 5678000000,
    },
]

CONTROLLER_DATA = {
    CONF_HOST: "mock-host",
    CONF_USERNAME: "mock-user",
    CONF_PASSWORD: "mock-pswd",
    CONF_PORT: 1234,
    CONF_SITE_ID: "mock-site",
    CONF_VERIFY_SSL: False,
}

ENTRY_CONFIG = {CONF_CONTROLLER: CONTROLLER_DATA}

CONTROLLER_ID = CONF_CONTROLLER_ID.format(host="mock-host", site="mock-site")

SITES = {"Site name": {"desc": "Site name", "name": "mock-site", "role": "admin"}}


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
    controller = hass.data[unifi.DOMAIN][controller_id]

    controller.mock_client_responses = mock_client_responses
    controller.mock_device_responses = mock_device_responses
    controller.mock_client_all_responses = mock_client_all_responses
    controller.mock_requests = mock_requests

    return controller


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a controller."""
    assert (
        await async_setup_component(
            hass, sensor.DOMAIN, {sensor.DOMAIN: {"platform": "unifi"}}
        )
        is True
    )
    assert unifi.DOMAIN not in hass.data


async def test_no_clients(hass):
    """Test the update_clients function when no clients are found."""
    controller = await setup_unifi_integration(
        hass,
        ENTRY_CONFIG,
        options={unifi.const.CONF_ALLOW_BANDWIDTH_SENSORS: True},
        sites=SITES,
        clients_response=[],
        devices_response=[],
        clients_all_response=[],
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 2


async def test_switches(hass):
    """Test the update_items function with some clients."""
    controller = await setup_unifi_integration(
        hass,
        ENTRY_CONFIG,
        options={
            unifi.const.CONF_ALLOW_BANDWIDTH_SENSORS: True,
            unifi.const.CONF_TRACK_CLIENTS: False,
            unifi.const.CONF_TRACK_DEVICES: False,
        },
        sites=SITES,
        clients_response=CLIENTS,
        devices_response=[],
        clients_all_response=[],
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 6

    wired_client_rx = hass.states.get("sensor.wired_client_name_rx")
    assert wired_client_rx.state == "1234.0"

    wired_client_tx = hass.states.get("sensor.wired_client_name_tx")
    assert wired_client_tx.state == "5678.0"

    wireless_client_rx = hass.states.get("sensor.wireless_client_name_rx")
    assert wireless_client_rx.state == "1234.0"

    wireless_client_tx = hass.states.get("sensor.wireless_client_name_tx")
    assert wireless_client_tx.state == "5678.0"

    clients = deepcopy(CLIENTS)
    clients[0]["is_wired"] = False
    clients[1]["rx_bytes"] = 2345000000
    clients[1]["tx_bytes"] = 6789000000

    controller.mock_client_responses.append(clients)
    await controller.async_update()
    await hass.async_block_till_done()

    wireless_client_rx = hass.states.get("sensor.wireless_client_name_rx")
    assert wireless_client_rx.state == "2345.0"

    wireless_client_tx = hass.states.get("sensor.wireless_client_name_tx")
    assert wireless_client_tx.state == "6789.0"
