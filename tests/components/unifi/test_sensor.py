"""UniFi sensor platform tests."""
from copy import deepcopy

from homeassistant.components import unifi
import homeassistant.components.sensor as sensor
from homeassistant.setup import async_setup_component

from .test_controller import setup_unifi_integration

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
        hass, options={unifi.const.CONF_ALLOW_BANDWIDTH_SENSORS: True},
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 1


async def test_sensors(hass):
    """Test the update_items function with some clients."""
    controller = await setup_unifi_integration(
        hass,
        options={
            unifi.const.CONF_ALLOW_BANDWIDTH_SENSORS: True,
            unifi.const.CONF_TRACK_CLIENTS: False,
            unifi.const.CONF_TRACK_DEVICES: False,
        },
        clients_response=CLIENTS,
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 5

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

    event = {"meta": {"message": "sta:sync"}, "data": clients}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    wireless_client_rx = hass.states.get("sensor.wireless_client_name_rx")
    assert wireless_client_rx.state == "2345.0"

    wireless_client_tx = hass.states.get("sensor.wireless_client_name_tx")
    assert wireless_client_tx.state == "6789.0"
