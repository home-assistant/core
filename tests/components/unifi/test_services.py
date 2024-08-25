"""deCONZ service tests."""

from typing import Any
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN as UNIFI_DOMAIN
from homeassistant.components.unifi.services import (
    SERVICE_RECONNECT_CLIENT,
    SERVICE_REMOVE_CLIENTS,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "client_payload", [[{"is_wired": False, "mac": "00:00:00:00:00:01"}]]
)
async def test_reconnect_client(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify call to reconnect client is performed as expected."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/cmd/stamgr",
    )

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, client_payload[0]["mac"])},
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1


@pytest.mark.usefixtures("config_entry_setup")
async def test_reconnect_non_existant_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify no call is made if device does not exist."""
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
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify no call is made if device does not have a known mac."""
    aioclient_mock.clear_requests()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={("other connection", "not mac")},
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "client_payload", [[{"is_wired": False, "mac": "00:00:00:00:00:01"}]]
)
async def test_reconnect_client_hub_unavailable(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify no call is made if hub is unavailable."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/cmd/stamgr",
    )

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, client_payload[0]["mac"])},
    )

    with patch(
        "homeassistant.components.unifi.UnifiHub.available", new_callable=PropertyMock
    ) as ws_mock:
        ws_mock.return_value = False
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
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify no call is made if trying to reconnect a mac unknown to hub."""
    aioclient_mock.clear_requests()
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "mac unknown to hub")},
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "client_payload", [[{"is_wired": True, "mac": "00:00:00:00:00:01"}]]
)
async def test_reconnect_wired_client(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify no call is made if client is wired."""
    aioclient_mock.clear_requests()
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, client_payload[0]["mac"])},
    )

    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "clients_all_payload",
    [
        [
            {
                "mac": "00:00:00:00:00:00",
            },
            {"first_seen": 100, "last_seen": 500, "mac": "00:00:00:00:00:01"},
            {"first_seen": 100, "last_seen": 1100, "mac": "00:00:00:00:00:02"},
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
    ],
)
async def test_remove_clients(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify removing different variations of clients work."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/cmd/stamgr",
    )

    await hass.services.async_call(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.mock_calls[0][2] == {
        "cmd": "forget-sta",
        "macs": ["00:00:00:00:00:00", "00:00:00:00:00:01"],
    }

    assert await hass.config_entries.async_unload(config_entry_setup.entry_id)


@pytest.mark.parametrize(
    "clients_all_payload",
    [
        [
            {
                "first_seen": 100,
                "last_seen": 500,
                "mac": "00:00:00:00:00:01",
            }
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_remove_clients_hub_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify no call is made if UniFi Network is unavailable."""
    aioclient_mock.clear_requests()
    with patch(
        "homeassistant.components.unifi.UnifiHub.available", new_callable=PropertyMock
    ) as ws_mock:
        ws_mock.return_value = False
        await hass.services.async_call(
            UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True
        )
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "clients_all_payload",
    [
        [
            {
                "first_seen": 100,
                "last_seen": 1100,
                "mac": "00:00:00:00:00:01",
            }
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_remove_clients_no_call_on_empty_list(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify no call is made if no fitting client has been added to the list."""
    aioclient_mock.clear_requests()
    await hass.services.async_call(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "clients_all_payload",
    [
        [
            {
                "first_seen": 100,
                "last_seen": 500,
                "mac": "00:00:00:00:00:01",
            }
        ]
    ],
)
async def test_services_handle_unloaded_config_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
    clients_all_payload: dict[str, Any],
) -> None:
    """Verify no call is made if config entry is unloaded."""
    await hass.config_entries.async_unload(config_entry_setup.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()

    await hass.services.async_call(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.call_count == 0

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, clients_all_payload[0]["mac"])},
    )
    await hass.services.async_call(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 0
