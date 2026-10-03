"""UniFi service tests."""

from typing import Any
from unittest.mock import PropertyMock, patch

import aiounifi
from aiounifi.models.network import Network
import pytest

from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN
from homeassistant.components.unifi.services import (
    ERROR_DUPLICATE_PRIORITY,
    SERVICE_RECONNECT_CLIENT,
    SERVICE_REMOVE_CLIENTS,
    SERVICE_SET_WAN_FAILOVER_ORDER,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_HOST, CONTENT_TYPE_JSON
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr

from .conftest import WAN_NETWORKS

from tests.common import MockConfigEntry, MockUser
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
        DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        service_data={ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1


@pytest.mark.usefixtures("config_entry_setup")
async def test_reconnect_non_existent_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify ServiceValidationError is raised if device does not exist."""
    aioclient_mock.clear_requests()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RECONNECT_CLIENT,
            service_data={ATTR_DEVICE_ID: "device_entry.id"},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "reconnect_client_device_not_found"
    assert aioclient_mock.call_count == 0


async def test_reconnect_device_without_mac(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify ServiceValidationError is raised if device does not have a known mac."""
    aioclient_mock.clear_requests()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={("other connection", "not mac")},
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RECONNECT_CLIENT,
            service_data={ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "reconnect_client_no_mac"
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
            DOMAIN,
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
        DOMAIN,
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
        DOMAIN,
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

    await hass.services.async_call(DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
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
        await hass.services.async_call(DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
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
    await hass.services.async_call(DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
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

    await hass.services.async_call(DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "client_payload", [[{"is_wired": False, "mac": "00:00:00:00:00:01"}]]
)
async def test_reconnect_client_request_failed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify HomeAssistantError is raised when API request fails."""
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, client_payload[0]["mac"])},
    )

    with (
        patch.object(
            config_entry_setup.runtime_data.api,
            "request",
            side_effect=aiounifi.AiounifiException,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RECONNECT_CLIENT,
            service_data={ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "reconnect_client_request_failed"


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
async def test_remove_clients_request_failed(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    clients_all_payload: list[dict[str, Any]],
) -> None:
    """Verify HomeAssistantError is raised when API request fails."""
    with (
        patch.object(
            config_entry_setup.runtime_data.api,
            "request",
            side_effect=aiounifi.AiounifiException,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(DOMAIN, SERVICE_REMOVE_CLIENTS, blocking=True)
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "remove_clients_request_failed"


def _wan_device_ids(
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    network_ids: list[str],
) -> list[str]:
    """Return device IDs of the WAN service devices."""
    device_ids = []
    for network_id in network_ids:
        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, network_id), config_entry.entry_id
        )
        assert device_entry is not None
        device_ids.append(device_entry.id)
    return device_ids


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
async def test_set_wan_failover_order(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify WAN networks are parked before being renumbered."""
    order = [WAN_NETWORKS[2]["_id"], WAN_NETWORKS[0]["_id"], WAN_NETWORKS[1]["_id"]]

    aioclient_mock.clear_requests()
    for network in WAN_NETWORKS:
        aioclient_mock.put(
            f"https://{config_entry_setup.data[CONF_HOST]}:1234"
            f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}"
            f"/rest/networkconf/{network['_id']}",
            json={"meta": {"rc": "ok"}, "data": []},
            headers={"content-type": CONTENT_TYPE_JSON},
        )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_WAN_FAILOVER_ORDER,
        service_data={
            ATTR_DEVICE_ID: _wan_device_ids(device_registry, config_entry_setup, order)
        },
        blocking=True,
    )

    # Every network is parked on a free priority before the order is applied
    assert [
        (call[1].path.rpartition("/")[2], call[2]["wan_failover_priority"])
        for call in aioclient_mock.mock_calls
    ] == [
        (order[0], 4),
        (order[1], 5),
        (order[2], 6),
        (order[0], 1),
        (order[1], 2),
        (order[2], 3),
    ]


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
@pytest.mark.parametrize(
    ("error_message", "expected_translation_key", "expected_placeholders"),
    [
        (ERROR_DUPLICATE_PRIORITY, "wan_failover_priority_conflict", None),
        (
            "api.err.Unknown",
            "set_wan_failover_order_failed",
            {"reason": "api.err.Unknown"},
        ),
    ],
)
async def test_set_wan_failover_order_request_failed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
    error_message: str,
    expected_translation_key: str,
    expected_placeholders: dict[str, str] | None,
) -> None:
    """Verify a failing request rolls back the captured priorities."""
    order = [WAN_NETWORKS[1]["_id"], WAN_NETWORKS[0]["_id"]]
    saved: list[tuple[str, int]] = []

    async def mock_save(network: Network, *, wan_failover_priority: int) -> None:
        """Fail once the second network is parked."""
        saved.append((network.id, wan_failover_priority))
        if len(saved) == 2:
            raise aiounifi.AiounifiException(
                {"meta": {"rc": "error", "msg": error_message}}
            )

    with (
        patch.object(
            config_entry_setup.runtime_data.api.networks, "save", side_effect=mock_save
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_WAN_FAILOVER_ORDER,
            service_data={
                ATTR_DEVICE_ID: _wan_device_ids(
                    device_registry, config_entry_setup, order
                )
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == expected_translation_key
    assert exc_info.value.translation_placeholders == expected_placeholders
    # Parking the second network failed, the captured priorities are restored
    assert saved == [
        (order[0], 4),
        (order[1], 5),
        (order[0], 6),
        (order[1], 7),
        (order[0], 2),
        (order[1], 1),
    ]


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
@pytest.mark.usefixtures("config_entry_setup")
async def test_set_wan_failover_order_unknown_device(hass: HomeAssistant) -> None:
    """Verify ServiceValidationError is raised for a device without a WAN network."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_WAN_FAILOVER_ORDER,
            service_data={ATTR_DEVICE_ID: ["not_a_device_id"]},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "wan_network_not_found"


@pytest.mark.parametrize(
    "network_payload", [[{**WAN_NETWORKS[0], "wan_failover_priority": None}]]
)
async def test_set_wan_failover_order_unsupported_network(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify ServiceValidationError is raised without a failover priority."""
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        identifiers={(DOMAIN, WAN_NETWORKS[0]["_id"])},
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_WAN_FAILOVER_ORDER,
            service_data={ATTR_DEVICE_ID: [device_entry.id]},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "wan_failover_priority_unsupported"


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
async def test_set_wan_failover_order_requires_admin(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
    hass_read_only_user: MockUser,
) -> None:
    """Verify a non admin user is not allowed to change the failover order."""
    device_ids = _wan_device_ids(
        device_registry, config_entry_setup, [WAN_NETWORKS[0]["_id"]]
    )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_WAN_FAILOVER_ORDER,
            service_data={ATTR_DEVICE_ID: device_ids},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
