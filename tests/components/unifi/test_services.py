"""deCONZ service tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN as UNIFI_DOMAIN
from homeassistant.components.unifi.services import (
    SERVICE_CHANGE_WLAN_PASSWORD,
    SERVICE_GET_WLAN_PASSWORD,
    SERVICE_RECONNECT_CLIENT,
    SERVICE_REMOVE_CLIENTS,
    SUPPORTED_SERVICES,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .test_hub import setup_unifi_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_service_setup_and_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify service setup works."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    for service in SUPPORTED_SERVICES:
        assert hass.services.has_service(UNIFI_DOMAIN, service)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    for service in SUPPORTED_SERVICES:
        assert not hass.services.has_service(UNIFI_DOMAIN, service)


@patch("homeassistant.core.ServiceRegistry.async_remove")
@patch("homeassistant.core.ServiceRegistry.async_register")
async def test_service_setup_and_unload_not_called_if_multiple_integrations_detected(
    register_service_mock,
    remove_service_mock,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Make sure that services are only setup and removed once."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    register_service_mock.reset_mock()
    config_entry_2 = await setup_unifi_integration(
        hass, aioclient_mock, config_entry_id=2
    )
    register_service_mock.assert_not_called()

    assert await hass.config_entries.async_unload(config_entry_2.entry_id)
    remove_service_mock.assert_not_called()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert remove_service_mock.call_count == 4


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
    hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
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
    hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
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


async def test_change_wlan_password_invalid_hub(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test changing WLAN password with an invalid Hub name."""
    hub_name_invalid = "Invalid Hub Name"
    wlan_name = "WLAN Test"
    old_password = "old123"
    new_password = "new456"

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        wlans_response=[
            {
                "_id": "12345",
                "name": wlan_name,
                "security": "wpa_psk",
                "x_passphrase": old_password,
                "enabled": True,
            }
        ],
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_CHANGE_WLAN_PASSWORD,
        service_data={
            "hub_name": hub_name_invalid,
            "wlan_name": wlan_name,
            "new_password": new_password,
        },
        blocking=True,
    )

    assert f"Hub '{hub_name_invalid}' not found" in caplog.text


async def test_change_wlan_password_invalid_wlan_name(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test changing WLAN password with an invalid WLAN name."""
    wlan_name = "WLAN Test"
    wlan_name_invalid = "WLAN Invalid"
    old_password = "old123"
    new_password = "new456"

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        wlans_response=[
            {
                "_id": "12345",
                "name": wlan_name,
                "security": "wpa_psk",
                "x_passphrase": old_password,
                "enabled": True,
            }
        ],
    )

    hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    hub_name = hub.config.entry.title

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_CHANGE_WLAN_PASSWORD,
        service_data={
            "hub_name": hub_name,
            "wlan_name": wlan_name_invalid,
            "new_password": new_password,
        },
        blocking=True,
    )

    assert (
        f"WLAN '{wlan_name_invalid}' not found in the Hub '{hub_name}'" in caplog.text
    )


async def test_change_wlan_password(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test changing WLAN password."""
    wlan_name = "WLAN Test"
    old_password = "old123"
    new_password = "new456"

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        wlans_response=[
            {
                "_id": "12345",
                "name": wlan_name,
                "security": "wpa_psk",
                "x_passphrase": old_password,
                "enabled": True,
            }
        ],
    )

    hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    hub_name = hub.config.entry.title

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_CHANGE_WLAN_PASSWORD,
        service_data={
            "hub_name": hub_name,
            "wlan_name": wlan_name,
            "new_password": new_password,
        },
        blocking=True,
    )

    assert (
        f"Password for WLAN Name '{wlan_name}' changed in Hub '{hub_name}' successfully"
        in caplog.text
    )


async def test_get_wlan_password_invalid_hub(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting WLAN password with an invalid Hub name."""
    hub_name_invalid = "Invalid Hub Name"
    wlan_name = "WLAN Test"
    password = "password123"

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        wlans_response=[
            {
                "_id": "12345",
                "name": wlan_name,
                "security": "wpa_psk",
                "x_passphrase": password,
                "enabled": True,
            }
        ],
    )

    response = await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_GET_WLAN_PASSWORD,
        service_data={"hub_name": hub_name_invalid, "wlan_name": wlan_name},
        blocking=True,
        return_response=True,
    )

    assert f"Hub '{hub_name_invalid}' not found" in caplog.text
    assert response == {}


async def test_get_wlan_password_invalid_wlan_name(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting WLAN password with an invalid WLAN name."""
    wlan_name = "WLAN Test"
    wlan_name_invalid = "WLAN Invalid"
    password = "password123"

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        wlans_response=[
            {
                "_id": "12345",
                "name": wlan_name,
                "security": "wpa_psk",
                "x_passphrase": password,
                "enabled": True,
            }
        ],
    )

    hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    hub_name = hub.config.entry.title

    response = await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_GET_WLAN_PASSWORD,
        service_data={"hub_name": hub_name, "wlan_name": wlan_name_invalid},
        blocking=True,
        return_response=True,
    )

    assert (
        f"WLAN '{wlan_name_invalid}' not found in the Hub '{hub_name}'" in caplog.text
    )
    assert response == {}


async def test_get_wlan_password(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting WLAN password."""
    wlan_name = "WLAN Test"
    password = "password123"
    expected = {"password": password}

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        wlans_response=[
            {
                "_id": "12345",
                "name": wlan_name,
                "security": "wpa_psk",
                "x_passphrase": password,
                "enabled": True,
            }
        ],
    )

    hub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    hub_name = hub.config.entry.title

    response = await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_GET_WLAN_PASSWORD,
        service_data={"hub_name": hub_name, "wlan_name": wlan_name},
        blocking=True,
        return_response=True,
    )

    assert (
        f"Retrieved password for WLAN Name '{wlan_name}' in Hub '{hub_name}' successfully"
        in caplog.text
    )
    assert response == expected
