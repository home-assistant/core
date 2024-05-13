"""Tests for Shelly update platform."""

from unittest.mock import AsyncMock, Mock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.shelly.const import (
    DOMAIN,
    GEN1_RELEASE_URL,
    GEN2_RELEASE_URL,
)
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_URL,
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
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    init_integration,
    inject_rpc_device_event,
    mock_rest_update,
    register_device,
    register_entity,
)

from tests.common import mock_restore_cache


async def test_block_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test block device update entity."""
    entity_id = "update.test_name_firmware_update"
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    await init_integration(hass, 1)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    supported_feat = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_feat == UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_block_device.trigger_ota_update.call_count == 1

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_RELEASE_URL] == GEN1_RELEASE_URL

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "2")
    await mock_rest_update(hass, freezer)

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-fwupdate"


async def test_block_beta_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test block device beta update entity."""
    entity_id = "update.test_name_beta_firmware_update"
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    monkeypatch.setitem(mock_block_device.status["update"], "beta_version", "")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    await init_integration(hass, 1)

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    monkeypatch.setitem(mock_block_device.status["update"], "beta_version", "2b")
    await mock_rest_update(hass, freezer)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_RELEASE_URL] is None

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_block_device.trigger_ota_update.call_count == 1

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is True

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "2b")
    await mock_rest_update(hass, freezer)

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2b"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-fwupdate_beta"


async def test_block_update_connection_error(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test block device update connection error."""
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
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test block device update authentication error."""
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    monkeypatch.setattr(
        mock_block_device,
        "trigger_ota_update",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1)

    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_rpc_update(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device update entity."""
    entity_id = "update.test_name_firmware_update"
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
        },
    )
    await init_integration(hass, 2)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    supported_feat = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_feat == UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_rpc_device.trigger_ota_update.call_count == 1

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_RELEASE_URL] == GEN2_RELEASE_URL

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_begin",
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] == 0

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_progress",
                    "id": 1,
                    "ts": 1668522399.2,
                    "progress_percent": 50,
                }
            ],
            "ts": 1668522399.2,
        },
    )

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] == 50

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_success",
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2")
    mock_rpc_device.mock_update()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-sys-fwupdate"


async def test_rpc_sleeping_update(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC sleeping device update entity."""
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
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
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)
    assert state.attributes[ATTR_RELEASE_URL] == GEN2_RELEASE_URL

    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2")
    mock_rpc_device.mock_update()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-sys-fwupdate"


async def test_rpc_restored_sleeping_update(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_reg: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
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
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    # Mock update
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)


async def test_rpc_restored_sleeping_update_no_last_state(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_reg: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
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
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    # Mock update
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)


async def test_rpc_beta_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test RPC device beta update entity."""
    entity_id = "update.test_name_beta_firmware_update"
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

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_RELEASE_URL] is None

    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": "2b"},
        },
    )
    await mock_rest_update(hass, freezer)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_begin",
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )

    assert mock_rpc_device.trigger_ota_update.call_count == 1

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] == 0

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_progress",
                    "id": 1,
                    "ts": 1668522399.2,
                    "progress_percent": 40,
                }
            ],
            "ts": 1668522399.2,
        },
    )

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] == 40

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_success",
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2b")
    await mock_rest_update(hass, freezer)

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2b"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-sys-fwupdate_beta"


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (DeviceConnectionError, "Error starting OTA update"),
        (RpcCallError(-1, "error"), "OTA update request error"),
    ],
)
async def test_rpc_update_errors(
    hass: HomeAssistant,
    exc: Exception,
    error: str,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test RPC device update connection/call errors."""
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
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test RPC device update authentication error."""
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

    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
