"""Tests for Shelly button platform."""

from copy import deepcopy
from unittest.mock import Mock

from aioshelly.const import MODEL_BLU_GATEWAY_G3
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, register_device, register_entity


async def test_block_button(
    hass: HomeAssistant, mock_block_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test block device reboot button."""
    await init_integration(hass, 1)

    entity_id = "button.test_name_reboot"

    # reboot button
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-reboot"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_block_device.trigger_reboot.call_count == 1


async def test_rpc_button(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test rpc device OTA button."""
    await init_integration(hass, 2)

    entity_id = "button.test_name_reboot"

    # reboot button
    assert (state := hass.states.get(entity_id))
    assert state == snapshot(name=f"{entity_id}-state")

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot(name=f"{entity_id}-entry")

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_rpc_device.trigger_reboot.call_count == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            DeviceConnectionError,
            "Device communication error occurred while calling action for button.test_name_reboot of Test name",
        ),
        (
            RpcCallError(999),
            "RPC call error occurred while calling action for button.test_name_reboot of Test name",
        ),
    ],
)
async def test_rpc_button_exc(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    exception: Exception,
    error: str,
) -> None:
    """Test RPC button with exception."""
    await init_integration(hass, 2)

    mock_rpc_device.trigger_reboot.side_effect = exception

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_name_reboot"},
            blocking=True,
        )


async def test_rpc_button_reauth_error(
    hass: HomeAssistant, mock_rpc_device: Mock
) -> None:
    """Test rpc device OTA button with authentication error."""
    entry = await init_integration(hass, 2)

    mock_rpc_device.trigger_reboot.side_effect = InvalidAuthError

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_name_reboot"},
        blocking=True,
    )

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


@pytest.mark.parametrize(
    ("gen", "old_unique_id", "new_unique_id", "migration"),
    [
        (2, "123456789ABC_reboot", "123456789ABC-reboot", True),
        (1, "123456789ABC_reboot", "123456789ABC-reboot", True),
        (2, "123456789ABC-reboot", "123456789ABC-reboot", False),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    gen: int,
    old_unique_id: str,
    new_unique_id: str,
    migration: bool,
) -> None:
    """Test migration of unique_id."""
    entry = await init_integration(hass, gen, skip_setup=True)

    entity = entity_registry.async_get_or_create(
        suggested_object_id="test_name_reboot",
        disabled_by=None,
        domain=BUTTON_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("button.test_name_reboot")
    assert entity_entry
    assert entity_entry.unique_id == new_unique_id

    assert (
        bool("Migrating unique_id for button.test_name_reboot" in caplog.text)
        == migration
    )


async def test_rpc_blu_trv_button(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test RPC BLU TRV button."""
    monkeypatch.delitem(mock_blu_trv.status, "script:1")
    monkeypatch.delitem(mock_blu_trv.status, "script:2")
    monkeypatch.delitem(mock_blu_trv.status, "script:3")

    await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    entity_id = "button.trv_name_calibrate"

    state = hass.states.get(entity_id)
    assert state == snapshot(name=f"{entity_id}-state")

    entry = entity_registry.async_get(entity_id)
    assert entry == snapshot(name=f"{entity_id}-entry")

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_blu_trv.trigger_blu_trv_calibration.call_count == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            DeviceConnectionError,
            "Device communication error occurred while calling action for button.trv_name_calibrate of Test name",
        ),
        (
            RpcCallError(999),
            "RPC call error occurred while calling action for button.trv_name_calibrate of Test name",
        ),
    ],
)
async def test_rpc_blu_trv_button_exc(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    error: str,
) -> None:
    """Test RPC BLU TRV button with exception."""
    monkeypatch.delitem(mock_blu_trv.status, "script:1")
    monkeypatch.delitem(mock_blu_trv.status, "script:2")
    monkeypatch.delitem(mock_blu_trv.status, "script:3")

    await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    mock_blu_trv.trigger_blu_trv_calibration.side_effect = exception

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.trv_name_calibrate"},
            blocking=True,
        )


async def test_rpc_blu_trv_button_auth_error(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC BLU TRV button with authentication error."""
    monkeypatch.delitem(mock_blu_trv.status, "script:1")
    monkeypatch.delitem(mock_blu_trv.status, "script:2")
    monkeypatch.delitem(mock_blu_trv.status, "script:3")

    entry = await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    mock_blu_trv.trigger_blu_trv_calibration.side_effect = InvalidAuthError

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.trv_name_calibrate"},
        blocking=True,
    )

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_rpc_device_virtual_button(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a virtual button for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["button:200"] = {
        "name": "Button",
        "meta": {"ui": {"view": "button"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["button:200"] = {"value": None}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)
    entity_id = "button.test_name_button"

    assert (state := hass.states.get(entity_id))
    assert state == snapshot(name=f"{entity_id}-state")

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot(name=f"{entity_id}-entry")

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.button_trigger.assert_called_once_with(200, "single_push")


async def test_rpc_remove_virtual_button_when_orphaned(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual button will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        BUTTON_DOMAIN,
        "test_name_button_200",
        "button:200",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


async def test_wall_display_virtual_button(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a Wall Display virtual button.

    Wall display does not have "meta" key in the config and defaults to "button" view.
    """
    config = deepcopy(mock_rpc_device.config)
    config["button:200"] = {"name": "Button"}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["button:200"] = {"value": None}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)
    entity_id = "button.test_name_button"

    assert (state := hass.states.get(entity_id))
    assert state == snapshot(name=f"{entity_id}-state")

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot(name=f"{entity_id}-entry")

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.button_trigger.assert_called_once_with(200, "single_push")


async def test_migrate_unique_id_blu_trv(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    entity_registry: EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test migration of unique_id for BLU TRV button."""
    entry = await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3, skip_setup=True)

    old_unique_id = "f8:44:77:25:f0:dd_calibrate"

    entity = entity_registry.async_get_or_create(
        suggested_object_id="trv_name_calibrate",
        disabled_by=None,
        domain=BUTTON_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("button.trv_name_calibrate")
    assert entity_entry
    assert entity_entry.unique_id == "F8447725F0DD-blutrv:200-calibrate"

    assert "Migrating unique_id for button.trv_name_calibrate" in caplog.text
