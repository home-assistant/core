"""Tests for Shelly update platform."""
from unittest.mock import AsyncMock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest

from homeassistant.components.shelly.const import DOMAIN
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateEntityFeature,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import async_get

from . import (
    MOCK_MAC,
    init_integration,
    mock_rest_update,
    register_device,
    register_entity,
)

from tests.common import mock_restore_cache


async def test_block_update(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device update entity."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    await init_integration(hass, 1)

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    supported_feat = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_feat == UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    assert mock_block_device.trigger_ota_update.call_count == 1

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is True

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "2")
    await mock_rest_update(hass)

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_block_beta_update(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device beta update entity."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-fwupdate_beta",
        suggested_object_id="test_name_beta_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    monkeypatch.setitem(mock_block_device.status["update"], "beta_version", "")
    await init_integration(hass, 1)

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    monkeypatch.setitem(mock_block_device.status["update"], "beta_version", "2b")
    await mock_rest_update(hass)

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_beta_firmware_update"},
        blocking=True,
    )
    assert mock_block_device.trigger_ota_update.call_count == 1

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is True

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "2b")
    await mock_rest_update(hass)

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2b"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_block_update_connection_error(
    hass: HomeAssistant,
    mock_block_device,
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test block device update connection error."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    monkeypatch.setattr(
        mock_block_device,
        "trigger_ota_update",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await init_integration(hass, 1)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
            blocking=True,
        )
        assert "Error starting OTA update" in caplog.text


async def test_block_update_auth_error(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device update authentication error."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    monkeypatch.setattr(
        mock_block_device,
        "trigger_ota_update",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1)

    assert entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_rpc_update(hass: HomeAssistant, mock_rpc_device, monkeypatch) -> None:
    """Test RPC device update entity."""
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
        },
    )
    await init_integration(hass, 2)

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    supported_feat = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_feat == UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    assert mock_rpc_device.trigger_ota_update.call_count == 1

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is True

    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2")
    mock_rpc_device.mock_update()

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_rpc_sleeping_update(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC sleeping device update entity."""
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
        },
    )
    entity_id = f"{UPDATE_DOMAIN}.test_name_firmware_update"
    await init_integration(hass, 2, sleep_period=1000)

    # Entity should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)

    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2")
    mock_rpc_device.mock_update()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)


async def test_rpc_restored_sleeping_update(
    hass: HomeAssistant, mock_rpc_device, device_reg, monkeypatch
) -> None:
    """Test RPC restored update entity."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass,
        UPDATE_DOMAIN,
        "test_name_firmware_update",
        "sys-fwupdate",
        entry,
    )

    attr = {ATTR_INSTALLED_VERSION: "1", ATTR_LATEST_VERSION: "2"}
    mock_restore_cache(hass, [State(entity_id, STATE_ON, attributes=attr)])
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2")
    monkeypatch.setitem(mock_rpc_device.status["sys"], "available_updates", {})
    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)


async def test_rpc_restored_sleeping_update_no_last_state(
    hass: HomeAssistant, mock_rpc_device, device_reg, monkeypatch
) -> None:
    """Test RPC restored update entity missing last state."""
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
        },
    )
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass,
        UPDATE_DOMAIN,
        "test_name_firmware_update",
        "sys-fwupdate",
        entry,
    )

    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)


async def test_rpc_beta_update(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC device beta update entity."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-sys-fwupdate_beta",
        suggested_object_id="test_name_beta_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": ""},
        },
    )
    await init_integration(hass, 2)

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": "2b"},
        },
    )
    await mock_rest_update(hass)

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_beta_firmware_update"},
        blocking=True,
    )
    assert mock_rpc_device.trigger_ota_update.call_count == 1

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is True

    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2b")
    await mock_rest_update(hass)

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2b"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (DeviceConnectionError, "Error starting OTA update"),
        (RpcCallError(-1, "error"), "OTA update request error"),
    ],
)
async def test_rpc_update__errors(
    hass: HomeAssistant,
    exc,
    error,
    mock_rpc_device,
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RPC device update connection/call errors."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-sys-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": ""},
        },
    )
    monkeypatch.setattr(
        mock_rpc_device, "trigger_ota_update", AsyncMock(side_effect=exc)
    )
    await init_integration(hass, 2)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
            blocking=True,
        )
        assert error in caplog.text


async def test_rpc_update_auth_error(
    hass: HomeAssistant, mock_rpc_device, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test RPC device update authentication error."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-sys-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": ""},
        },
    )
    monkeypatch.setattr(
        mock_rpc_device,
        "trigger_ota_update",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 2)

    assert entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
