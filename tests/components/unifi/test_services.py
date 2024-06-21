"""deCONZ service tests."""

from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN as UNIFI_DOMAIN
from homeassistant.components.unifi.services import (
    SERVICE_RECONNECT_CLIENT,
    SERVICE_REMOVE_CLIENTS,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .test_hub import setup_unifi_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_reconnect_client(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Verify call to reconnect client is performed as expected."""
    clients = [
        {
            "is_wired": False,
            "mac": "00:00:00:00:00:01",
        }
    ]
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_response=clients
    )

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry.data[CONF_SITE_ID]}/cmd/stamgr",
    )

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, clients[0]["mac"])},
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1


async def test_reconnect_non_existant_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify no call is made if device does not exist."""
    await setup_unifi_integration(hass, aioclient_mock)

    aioclient_mock.clear_requests()

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: "device_entry.id"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 0


async def test_reconnect_device_without_mac(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Verify no call is made if device does not have a known mac."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)

    aioclient_mock.clear_requests()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={("other connection", "not mac")},
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 0


async def test_reconnect_client_hub_unavailable(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Verify no call is made if hub is unavailable."""
    clients = [
        {
            "is_wired": False,
            "mac": "00:00:00:00:00:01",
        }
    ]
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_response=clients
    )
    hub = config_entry.runtime_data
    hub.websocket.available = False

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry.data[CONF_SITE_ID]}/cmd/stamgr",
    )

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, clients[0]["mac"])},
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 0


async def test_reconnect_client_unknown_mac(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Verify no call is made if trying to reconnect a mac unknown to hub."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)

    aioclient_mock.clear_requests()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "mac unknown to hub")},
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 0


async def test_reconnect_wired_client(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Verify no call is made if client is wired."""
    clients = [
        {
            "is_wired": True,
            "mac": "00:00:00:00:00:01",
        }
    ]
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_response=clients
    )

    aioclient_mock.clear_requests()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, clients[0]["mac"])},
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 0


async def test_remove_clients(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify removing different variations of clients work."""
    clients = [
        {
            "mac": "00:00:00:00:00:00",
        },
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

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry.data[CONF_SITE_ID]}/cmd/stamgr",
    )

    await hass.services.async_call(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.mock_calls[0][2] == {
        "cmd": "forget-sta",
        "macs": ["00:00:00:00:00:00", "00:00:00:00:00:01"],
    }

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_remove_clients_hub_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify no call is made if UniFi Network is unavailable."""
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
    hub = config_entry.runtime_data
    hub.websocket.available = False

    aioclient_mock.clear_requests()

    await hass.services.async_call(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.call_count == 0


async def test_remove_clients_no_call_on_empty_list(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify no call is made if no fitting client has been added to the list."""
    clients = [
        {
            "first_seen": 100,
            "last_seen": 1100,
            "mac": "00:00:00:00:00:01",
        }
    ]
    await setup_unifi_integration(hass, aioclient_mock, clients_all_response=clients)

    aioclient_mock.clear_requests()

    await hass.services.async_call(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.call_count == 0
