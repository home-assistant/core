"""The tests for the UniFi Network update platform."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any
from unittest.mock import patch

import aiounifi
from aiounifi.models.message import MessageKey
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion
from yarl import URL

from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

# Device with new firmware available
DEVICE_1 = {
    "board_rev": 3,
    "device_id": "mock-id",
    "ip": "10.0.1.1",
    "last_seen": 1562600145,
    "mac": "00:00:00:00:01:01",
    "model": "US16P150",
    "name": "Device 1",
    "next_interval": 20,
    "state": 1,
    "type": "usw",
    "upgradable": True,
    "version": "4.0.42.10433",
    "upgrade_to_firmware": "4.3.17.11279",
}

# Device without new firmware available
DEVICE_2 = {
    "board_rev": 3,
    "device_id": "mock-id",
    "ip": "10.0.1.2",
    "mac": "00:00:00:00:01:02",
    "model": "US16P150",
    "name": "Device 2",
    "next_interval": 20,
    "state": 0,
    "type": "usw",
    "version": "4.0.42.10433",
}

# Gateway with an IPS engine upgrade queued
GATEWAY_IPS = {
    "device_id": "mock-gateway-id",
    "ip": "10.0.0.1",
    "mac": "00:00:00:00:02:01",
    "model": "UDMA6A8",
    "name": "Gateway",
    "state": 1,
    "type": "udm",
    "version": "5.0.16.30692",
    "suricata_version": 6,
    "supported_suricata_version": 8,
    "suricata_upgrade_pending_target": 8,
}
IPS_ENGINE_ENTITY_ID = "update.gateway_ips_engine"


@pytest.mark.parametrize("device_payload", [[DEVICE_1, DEVICE_2, GATEWAY_IPS]])
@pytest.mark.parametrize(
    "site_payload",
    [
        [{"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}],
        [{"desc": "Site name", "name": "site_id", "role": "not admin", "_id": "1"}],
    ],
)
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data with and without admin rights."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.UPDATE]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_updates(
    hass: HomeAssistant, mock_websocket_message: WebsocketMessageMock
) -> None:
    """Test the update_items function with some devices."""
    device_1_state = hass.states.get("update.device_1_firmware")
    assert device_1_state.state == STATE_ON
    assert device_1_state.attributes[ATTR_IN_PROGRESS] is False

    # Simulate start of update

    device_1 = deepcopy(DEVICE_1)
    device_1["state"] = 4
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)

    device_1_state = hass.states.get("update.device_1_firmware")
    assert device_1_state.state == STATE_ON
    assert device_1_state.attributes[ATTR_INSTALLED_VERSION] == "4.0.42.10433"
    assert device_1_state.attributes[ATTR_LATEST_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_IN_PROGRESS] is True

    # Simulate update finished

    device_1["state"] = 0
    device_1["version"] = "4.3.17.11279"
    device_1["upgradable"] = False
    del device_1["upgrade_to_firmware"]
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)

    device_1_state = hass.states.get("update.device_1_firmware")
    assert device_1_state.state == STATE_OFF
    assert device_1_state.attributes[ATTR_INSTALLED_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_LATEST_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
async def test_install(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test the device update install call."""
    device_state = hass.states.get("update.device_1_firmware")
    assert device_state.state == STATE_ON

    url = (
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/cmd/devmgr"
    )
    aioclient_mock.clear_requests()
    aioclient_mock.post(url)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.device_1_firmware"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0] == (
        "post",
        URL(url),
        {"cmd": "upgrade", "mac": "00:00:00:00:01:01"},
        {},
    )


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_hub_state_change(
    hass: HomeAssistant, mock_websocket_state: WebsocketStateManager
) -> None:
    """Verify entities state reflect on hub becoming unavailable."""
    assert hass.states.get("update.device_1_firmware").state == STATE_ON

    # Controller unavailable
    await mock_websocket_state.disconnect()
    assert hass.states.get("update.device_1_firmware").state == STATE_UNAVAILABLE

    # Controller available
    await mock_websocket_state.reconnect()
    assert hass.states.get("update.device_1_firmware").state == STATE_ON


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
async def test_install_request_failed(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify HomeAssistantError is raised when install API request fails."""
    with (
        patch.object(
            config_entry_setup.runtime_data.api,
            "request",
            side_effect=aiounifi.AiounifiException,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.device_1_firmware"},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "action_request_failed"


@pytest.mark.parametrize("device_payload", [[GATEWAY_IPS]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_ips_engine_updates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Test the IPS engine entity follows the gateway and is retained."""
    assert hass.states.get(IPS_ENGINE_ENTITY_ID).state == STATE_ON
    registry_entry = entity_registry.async_get(IPS_ENGINE_ENTITY_ID)

    # Newer engine supported, but no upgrade queued
    gateway = deepcopy(GATEWAY_IPS)
    del gateway["suricata_upgrade_pending_target"]
    mock_websocket_message(message=MessageKey.DEVICE, data=gateway)

    state = hass.states.get(IPS_ENGINE_ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "6"
    assert state.attributes[ATTR_LATEST_VERSION] == "6"

    # Queued engine upgrade applied
    gateway["suricata_version"] = 8
    mock_websocket_message(message=MessageKey.DEVICE, data=gateway)

    state = hass.states.get(IPS_ENGINE_ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "8"
    assert state.attributes[ATTR_LATEST_VERSION] == "8"

    # Engine no longer reported, the entity is retained
    del gateway["suricata_version"]
    del gateway["supported_suricata_version"]
    mock_websocket_message(message=MessageKey.DEVICE, data=gateway)
    await hass.async_block_till_done()

    state = hass.states.get(IPS_ENGINE_ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_INSTALLED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] is None
    assert entity_registry.async_get(IPS_ENGINE_ENTITY_ID) == registry_entry

    # Engine reported again
    mock_websocket_message(message=MessageKey.DEVICE, data=GATEWAY_IPS)

    assert hass.states.get(IPS_ENGINE_ENTITY_ID).state == STATE_ON


@pytest.mark.parametrize(
    "device_payload",
    [[{key: value for key, value in GATEWAY_IPS.items() if "suricata" not in key}]],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_ips_engine_reported_after_setup(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Test the IPS engine entity is added when a known gateway reports it."""
    assert hass.states.get(IPS_ENGINE_ENTITY_ID) is None

    mock_websocket_message(message=MessageKey.DEVICE, data=GATEWAY_IPS)
    await hass.async_block_till_done()

    assert hass.states.get(IPS_ENGINE_ENTITY_ID).state == STATE_ON


@pytest.mark.parametrize("device_payload", [[deepcopy(GATEWAY_IPS)]])
async def test_ips_engine_restored_after_reload(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    mock_requests: Callable[[], None],
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
) -> None:
    """Test a registered IPS engine entity is restored while not reported."""
    registry_entry = entity_registry.async_get(IPS_ENGINE_ENTITY_ID)

    for key in list(device_payload[0]):
        if "suricata" in key:
            del device_payload[0][key]
    aioclient_mock.clear_requests()
    mock_requests()
    await hass.config_entries.async_reload(config_entry_setup.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(IPS_ENGINE_ENTITY_ID).state == STATE_UNKNOWN
    assert entity_registry.async_get(IPS_ENGINE_ENTITY_ID) == registry_entry

    mock_websocket_message(message=MessageKey.DEVICE, data=GATEWAY_IPS)
    await hass.async_block_till_done()

    assert hass.states.get(IPS_ENGINE_ENTITY_ID).state == STATE_ON
