"""The tests for the UniFi Network update platform."""

from collections.abc import Callable
from copy import deepcopy
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
    UpdateService,
)
from homeassistant.const import (
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    CommonServiceArgument,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
async def test_device_updates(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Test the update_items function with some devices."""
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, DEVICE_1["mac"]), config_entry_setup.entry_id
    )
    assert device_entry is not None
    assert device_entry.sw_version == "4.0.42.10433"

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
    updated_device_entry = device_registry.async_get(device_entry.id)
    assert updated_device_entry is not None
    assert updated_device_entry.sw_version == "4.3.17.11279"


@pytest.mark.parametrize("device_payload", [[GATEWAY_IPS]], indirect=True)
async def test_device_version_updates_without_update_entities(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Keep firmware metadata current without enabled update entities."""
    entity_registry.async_update_entity(
        "update.gateway_firmware", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert hass.states.get("update.gateway_firmware") is None
    assert hass.states.get(IPS_ENGINE_ENTITY_ID) is None
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, GATEWAY_IPS["mac"]),
        config_entry_setup.entry_id,
    )
    assert device_entry is not None

    with (
        patch.object(
            device_registry,
            "async_get_device_by_connection",
            wraps=device_registry.async_get_device_by_connection,
        ) as get_device,
        patch.object(
            device_registry,
            "async_update_device",
            wraps=device_registry.async_update_device,
        ) as update_device,
    ):
        mock_websocket_message(
            message=MessageKey.DEVICE, data={**GATEWAY_IPS, "uptime": 100}
        )
        get_device.assert_not_called()
        update_device.assert_not_called()

        upgraded_device = {**GATEWAY_IPS, "version": "5.0.16.30693"}
        mock_websocket_message(message=MessageKey.DEVICE, data=upgraded_device)
        get_device.assert_called_once_with(
            (dr.CONNECTION_NETWORK_MAC, GATEWAY_IPS["mac"]),
            config_entry_setup.entry_id,
        )
        update_device.assert_called_once_with(
            device_entry.id, sw_version="5.0.16.30693"
        )

        mock_websocket_message(
            message=MessageKey.DEVICE, data={**upgraded_device, "uptime": 200}
        )
        get_device.assert_called_once()
        update_device.assert_called_once()

    updated_device_entry = device_registry.async_get(device_entry.id)
    assert updated_device_entry is not None
    assert updated_device_entry.sw_version == "5.0.16.30693"


@pytest.mark.parametrize("device_payload", [[GATEWAY_IPS]], indirect=True)
async def test_device_version_reconciled_on_recovery_and_reload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    device_payload: list[dict[str, str | int]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_requests: Callable[[], None],
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Reconcile firmware metadata after missed updates and on initial load."""
    entity_registry.async_update_entity(
        "update.gateway_firmware", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, GATEWAY_IPS["mac"]),
        config_entry_setup.entry_id,
    )
    assert device_entry is not None

    await mock_websocket_state.disconnect()
    device_payload[0] = {**GATEWAY_IPS, "version": "5.0.16.30693"}
    aioclient_mock.clear_requests()
    await mock_websocket_state.reconnect()

    updated_device_entry = device_registry.async_get(device_entry.id)
    assert updated_device_entry is not None
    assert updated_device_entry.sw_version == "5.0.16.30693"

    device_registry.async_update_device(device_entry.id, sw_version="outdated")
    aioclient_mock.clear_requests()
    mock_requests()
    await hass.config_entries.async_reload(config_entry_setup.entry_id)
    await hass.async_block_till_done()

    updated_device_entry = device_registry.async_get(device_entry.id)
    assert updated_device_entry is not None
    assert updated_device_entry.sw_version == "5.0.16.30693"
    assert hass.states.get("update.gateway_firmware") is None
    assert hass.states.get(IPS_ENGINE_ENTITY_ID) is None


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
        UpdateService.INSTALL,
        {CommonServiceArgument.ENTITY_ID: "update.device_1_firmware"},
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
            UpdateService.INSTALL,
            {CommonServiceArgument.ENTITY_ID: "update.device_1_firmware"},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "action_request_failed"


@pytest.mark.parametrize("device_payload", [[GATEWAY_IPS]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_ips_engine_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the IPS engine entity is disabled by default."""
    assert hass.states.get(IPS_ENGINE_ENTITY_ID) is None
    entry = entity_registry.async_get(IPS_ENGINE_ENTITY_ID)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("device_payload", [[GATEWAY_IPS]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "config_entry_setup")
async def test_ips_engine_updates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Test the IPS engine entity follows the gateway."""
    assert hass.states.get(IPS_ENGINE_ENTITY_ID).state == STATE_ON

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

    # Engine no longer reported, the entity is removed
    del gateway["suricata_version"]
    del gateway["supported_suricata_version"]
    mock_websocket_message(message=MessageKey.DEVICE, data=gateway)
    await hass.async_block_till_done()

    assert hass.states.get(IPS_ENGINE_ENTITY_ID) is None
    assert entity_registry.async_get(IPS_ENGINE_ENTITY_ID) is None
