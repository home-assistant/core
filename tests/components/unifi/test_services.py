"""deCONZ service tests."""

from unittest.mock import Mock, patch

from homeassistant.components.unifi.const import DOMAIN as UNIFI_DOMAIN
from homeassistant.components.unifi.services import (
    SERVICE_REMOVE_CLIENTS,
    UNIFI_SERVICES,
    async_setup_services,
    async_unload_services,
)

from .test_controller import setup_unifi_integration


async def test_service_setup(hass):
    """Verify service setup works."""
    assert UNIFI_SERVICES not in hass.data
    with patch(
        "homeassistant.core.ServiceRegistry.async_register", return_value=Mock(True)
    ) as async_register:
        await async_setup_services(hass)
        assert hass.data[UNIFI_SERVICES] is True
        assert async_register.call_count == 1


async def test_service_setup_already_registered(hass):
    """Make sure that services are only registered once."""
    hass.data[UNIFI_SERVICES] = True
    with patch(
        "homeassistant.core.ServiceRegistry.async_register", return_value=Mock(True)
    ) as async_register:
        await async_setup_services(hass)
        async_register.assert_not_called()


async def test_service_unload(hass):
    """Verify service unload works."""
    hass.data[UNIFI_SERVICES] = True
    with patch(
        "homeassistant.core.ServiceRegistry.async_remove", return_value=Mock(True)
    ) as async_remove:
        await async_unload_services(hass)
        assert hass.data[UNIFI_SERVICES] is False
        assert async_remove.call_count == 1


async def test_service_unload_not_registered(hass):
    """Make sure that services can only be unloaded once."""
    with patch(
        "homeassistant.core.ServiceRegistry.async_remove", return_value=Mock(True)
    ) as async_remove:
        await async_unload_services(hass)
        assert UNIFI_SERVICES not in hass.data
        async_remove.assert_not_called()


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
