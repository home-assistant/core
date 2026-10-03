"""Exercise the published client through HTTP responses and real Core setup."""

from copy import deepcopy
from ipaddress import ip_address
import json
from unittest.mock import patch

from aiohttp import ClientConnectionError
import pytest

from homeassistant.components.lanbon.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import GATEWAY_ID, HOST, INFO, PORT, SNAPSHOT, TOKEN

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

BASE = f"http://{HOST}:{PORT}/api/v1"
USER_INPUT = {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN}
DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(HOST),
    ip_addresses=[ip_address(HOST)],
    port=PORT,
    hostname="lanbon.local.",
    type="_lanbon._tcp.local.",
    name="L10-4G._lanbon._tcp.local.",
    properties={"id": GATEWAY_ID, "token": "ignored-mdns-token"},
)


@pytest.mark.parametrize(
    ("source", "discovery", "user_input"),
    [
        (SOURCE_USER, None, USER_INPUT),
        (SOURCE_ZEROCONF, DISCOVERY, {CONF_TOKEN: TOKEN}),
    ],
)
@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, "", "invalid_auth"),
        (403, "{}", "unknown"),
        (429, "{}", "unknown"),
        (500, "{}", "unknown"),
        (200, "not-json", "cannot_connect"),
        (200, "[]", "cannot_connect"),
        (200, json.dumps({**INFO, "api_enabled": False}), "api_disabled"),
        (200, json.dumps({**INFO, "limits": {"max_devices": "bad"}}), "unknown"),
    ],
)
async def test_http_config_flow_error_and_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    source: str,
    discovery: ZeroconfServiceInfo | None,
    user_input: dict[str, str | int],
    status: int,
    body: str,
    error: str,
) -> None:
    """Real response parsing returns an error form and accepts a corrected retry."""
    aioclient_mock.get(f"{BASE}/info", status=status, text=body)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(aioclient_mock.mock_calls[0][1])
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/info", json=INFO)
    with patch("homeassistant.components.lanbon.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == TOKEN


@pytest.mark.parametrize(
    ("source", "discovery", "user_input"),
    [
        pytest.param(SOURCE_USER, None, USER_INPUT, id="user"),
        pytest.param(SOURCE_ZEROCONF, DISCOVERY, {CONF_TOKEN: TOKEN}, id="zeroconf"),
    ],
)
@pytest.mark.parametrize("gateway_id", ["", None])
async def test_http_config_flow_requires_authenticated_gateway_id(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    source: str,
    discovery: ZeroconfServiceInfo | None,
    user_input: dict[str, str | int],
    gateway_id: str | None,
) -> None:
    """An advertised ID cannot replace a missing ID in the API response."""
    aioclient_mock.get(f"{BASE}/info", json={**INFO, "gateway_id": gateway_id})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_unique_id"
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("events", ["polling", "websocket"])
async def test_http_disabled_api_blocks_setup_and_recovers(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    events: str,
) -> None:
    """Existing entries must respect Open Integration before fetching devices."""
    aioclient_mock.get(
        f"{BASE}/info",
        json={
            **INFO,
            "api_enabled": False,
            "transports": {"http": True, "events": events},
        },
    )
    aioclient_mock.get(f"{BASE}/devices", json=SNAPSHOT)
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == "Open Integration is disabled"
    assert not hass.states.async_all("switch")
    assert len(aioclient_mock.mock_calls) == 1

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/info", json=INFO)
    aioclient_mock.get(f"{BASE}/devices", json=SNAPSHOT)
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_all("switch")
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_http_registers_gateway_and_child_mac_connections(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """LOIP Wi-Fi MAC IDs identify both gateway and child network connections."""
    devices = deepcopy(SNAPSHOT)
    child = deepcopy(devices["devices"][0])
    child.update(id="aabbccddeeff", role="child", name="Child")
    devices["devices"].append(child)
    aioclient_mock.get(f"{BASE}/info", json=INFO)
    aioclient_mock.get(f"{BASE}/devices", json=devices)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    gateway = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, "dc:da:0c:3b:c7:14"), mock_config_entry.entry_id
    )
    child_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff"), mock_config_entry.entry_id
    )
    assert gateway is not None
    assert child_device is not None
    assert child_device.id != gateway.id
    assert child_device.via_device_id == gateway.id
    assert len(hass.states.async_all("switch")) == 2
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


@pytest.mark.parametrize("error", [TimeoutError(), ClientConnectionError("offline")])
async def test_http_connection_error_and_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    error: Exception,
) -> None:
    """Transport exceptions are translated by the actual dependency."""
    aioclient_mock.get(f"{BASE}/info", exc=error)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["errors"] == {"base": "cannot_connect"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/info", json=INFO)
    with patch("homeassistant.components.lanbon.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_http_setup_control_refresh_and_unload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The real dependency connects Core setup, commands, JSON and HTTP 304."""
    aioclient_mock.get(f"{BASE}/info", json=INFO)
    aioclient_mock.get(f"{BASE}/devices", json=SNAPSHOT)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = hass.states.async_entity_ids("switch")[0]
    assert hass.states.get(entity_id).state == STATE_OFF
    changed = deepcopy(SNAPSHOT)
    changed["revision"] = "2"
    changed["devices"][0]["components"][0]["state"]["on"] = True
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{BASE}/command", json={"ok": True, "revision": "2"})
    aioclient_mock.get(f"{BASE}/devices", json=changed)
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    command = json.loads(aioclient_mock.mock_calls[0][2])
    assert command["device_id"] == GATEWAY_ID
    assert command["component_id"] == "switch:1"
    assert command["command"] == "set_on"
    assert command["params"] == {"on": True}
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {TOKEN}"
    assert hass.states.get(entity_id).state == STATE_ON
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/devices", status=304)
    await mock_config_entry.runtime_data.async_refresh()
    assert aioclient_mock.mock_calls[0][3]["If-None-Match"] == '"2"'
    assert hass.states.get(entity_id).state == STATE_ON
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


@pytest.mark.parametrize("status", [200, 503])
async def test_http_command_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    status: int,
) -> None:
    """HTTP success with ok=false must still fail the Home Assistant action."""
    aioclient_mock.get(f"{BASE}/info", json=INFO)
    aioclient_mock.get(f"{BASE}/devices", json=SNAPSHOT)
    aioclient_mock.post(
        f"{BASE}/command",
        status=status,
        json={"ok": False, "error": {"code": "device_offline", "message": "offline"}},
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = hass.states.async_entity_ids("switch")[0]
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": entity_id}, blocking=True
        )
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    ("status", "state"),
    [(401, ConfigEntryState.SETUP_ERROR), (503, ConfigEntryState.SETUP_RETRY)],
)
async def test_http_setup_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    status: int,
    state: ConfigEntryState,
) -> None:
    """Authentication and transient HTTP failures reach Core setup correctly."""
    aioclient_mock.get(f"{BASE}/info", status=status, json={})
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is state


@pytest.mark.parametrize(
    ("info_gateway", "request_count"),
    [("foreign", 1), (GATEWAY_ID, 2)],
    ids=["info", "devices"],
)
async def test_http_foreign_gateway_cannot_set_up(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    info_gateway: str,
    request_count: int,
) -> None:
    """Published-client JSON parsing must not admit another gateway at our address."""
    info = {**INFO, "gateway_id": info_gateway}
    devices = {**SNAPSHOT, "gateway_id": "foreign"}
    aioclient_mock.get(f"{BASE}/info", json=info)
    aioclient_mock.get(f"{BASE}/devices", json=devices)
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_all("switch")
    assert len(aioclient_mock.mock_calls) == request_count
    assert mock_config_entry.unique_id == GATEWAY_ID
