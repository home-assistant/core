"""deCONZ service tests."""

from unittest.mock import patch

from homeassistant.components.unifi.const import DOMAIN as UNIFI_DOMAIN
from homeassistant.components.unifi.services import SERVICE_REMOVE_CLIENTS

from .test_controller import setup_unifi_integration


@patch("homeassistant.components.unifi.async_unload_services")
@patch("homeassistant.components.unifi.async_setup_services")
async def test_service_setup_and_unload(
    setup_unifi_services_mock, unload_unifi_services_mock, hass, aioclient_mock
):
    """Verify service setup works."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    assert setup_unifi_services_mock.call_count == 1

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert unload_unifi_services_mock.call_count == 1


@patch("homeassistant.components.unifi.async_unload_services")
@patch("homeassistant.components.unifi.async_setup_services")
async def test_service_setup_and_unload_not_called_if_multiple_integrations_detected(
    setup_unifi_services_mock, unload_unifi_services_mock, hass, aioclient_mock
):
    """Make sure that services are only setup and removed once."""
    hass.data[UNIFI_DOMAIN] = {"integration setup": True}

    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    setup_unifi_services_mock.assert_not_called()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    unload_unifi_services_mock.assert_not_called()


async def test_remove_clients(hass, aioclient_mock):
    """Verify removing different variations of clients work."""
    clients = [
        {
            "first_seen": 100,
            "last_seen": 500,
            "mac": "00:00:00:00:00:01",
        },
        {
            "first_seen": 100,
            "last_seen": 1100,
            "mac": "00:00:00:00:00:02",
        },
        {
            "first_seen": 100,
            "last_seen": 500,
            "fixed_ip": "1.2.3.4",
            "mac": "00:00:00:00:00:03",
        },
        {
            "first_seen": 100,
            "last_seen": 500,
            "hostname": "hostname",
            "mac": "00:00:00:00:00:04",
        },
        {
            "first_seen": 100,
            "last_seen": 500,
            "name": "name",
            "mac": "00:00:00:00:00:05",
        },
    ]
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_all_response=clients
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{controller.host}:1234/api/s/{controller.site}/cmd/stamgr",
    )

    await hass.services.async_call(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.mock_calls[0][2] == {
        "cmd": "forget-sta",
        "macs": ["00:00:00:00:00:01"],
    }

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_remove_clients_controller_unavailable(hass, aioclient_mock):
    """Verify no call is made if controller is unavailable."""
    clients = [
        {
            "first_seen": 100,
            "last_seen": 500,
            "mac": "00:00:00:00:00:01",
        }
    ]
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_all_response=clients
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.available = False

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{controller.host}:1234/api/s/{controller.site}/cmd/stamgr",
    )

    await hass.services.async_call(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.call_count == 0


async def test_remove_clients_no_call_on_empty_list(hass, aioclient_mock):
    """Verify no call is made if no fitting client has been added to the list."""
    clients = [
        {
            "first_seen": 100,
            "last_seen": 1100,
            "mac": "00:00:00:00:00:01",
        }
    ]
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_all_response=clients
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{controller.host}:1234/api/s/{controller.site}/cmd/stamgr",
    )

    await hass.services.async_call(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.call_count == 0
