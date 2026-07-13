"""Tests for Shelly button platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, Mock, patch

from aioshelly.const import MODEL_BLU_GATEWAY_G3, MODEL_PLUS_SMOKE, MODEL_WALL_DISPLAY
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    init_integration,
    mutate_rpc_device_status,
    patch_platforms,
    register_device,
    register_entity,
)


@pytest.fixture(autouse=True)
def fixture_platforms():
    """Limit platforms under test."""
    with patch_platforms([Platform.BUTTON]):
        yield


async def test_block_button(
    hass: HomeAssistant, mock_block_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test block device reboot button."""
    await init_integration(hass, 1)

    entity_id = "button.test_name_restart"

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

    entity_id = "button.test_name_restart"

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
            "Device communication error occurred while calling action"
            " for button.test_name_restart of Test name",
        ),
        (
            RpcCallError(999),
            "RPC call error occurred while calling action"
            " for button.test_name_restart of Test name",
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
            {ATTR_ENTITY_ID: "button.test_name_restart"},
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
        {ATTR_ENTITY_ID: "button.test_name_restart"},
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
    mock_blu_trv.trigger_blu_trv_calibration.assert_called_once_with(200)


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            DeviceConnectionError,
            "Device communication error occurred while calling action"
            " for button.trv_name_calibrate of Test name",
        ),
        (
            RpcCallError(999),
            "RPC call error occurred while calling action"
            " for button.trv_name_calibrate of Test name",
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
    """Test virtual button removal from device configuration."""
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


async def test_rpc_smoke_mute_alarm_button(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC smoke mute alarm button."""
    entity_id = f"{BUTTON_DOMAIN}.test_name_mute_alarm"
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    monkeypatch.setattr(mock_rpc_device, "config", {"smoke:0": {"id": 0, "name": None}})
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    with patch.object(
        mock_rpc_device,
        "initialize",
        new_callable=AsyncMock,
        side_effect=DeviceConnectionError,
    ):
        await init_integration(hass, 2, sleep_period=1000, model=MODEL_PLUS_SMOKE)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "smoke:0", "alarm", True)
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    mock_rpc_device.smoke_mute_alarm.assert_called_once_with(0)

    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(("action", "value"), [("turn_on", True), ("turn_off", False)])
async def test_wall_display_screen_buttons(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    snapshot: SnapshotAssertion,
    action: str,
    value: bool,
) -> None:
    """Test a Wall Display screen buttons."""
    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)
    entity_id = f"button.test_name_{action}_the_screen"

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
    mock_rpc_device.wall_display_set_screen.assert_called_once_with(value=value)


async def test_rpc_remove_restart_button_for_sleeping_devices(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC remove restart button for sleeping devices."""
    config_entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        BUTTON_DOMAIN,
        "test_name_restart",
        "reboot",
        config_entry,
        device_id=device_entry.id,
    )

    assert entity_registry.async_get(entity_id) is not None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None
