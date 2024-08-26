"""Tests for Shelly number platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, Mock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError
import pytest

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
    NumberMode,
)
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, register_device, register_entity

from tests.common import mock_restore_cache_with_extra_data

DEVICE_BLOCK_ID = 4


async def test_block_number_update(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device number update."""
    entity_id = "number.test_name_valve_position"
    monkeypatch.setitem(
        mock_block_device.settings,
        "sleep_mode",
        {"period": 60, "unit": "m"},
    )
    await init_integration(hass, 1, sleep_period=3600)

    assert hass.states.get(entity_id) is None

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "50"

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "valvePos", 30)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == "30"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-device_0-valvePos"


async def test_block_restored_number(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored number."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    capabilities = {
        "min": 0,
        "max": 100,
        "step": 1,
        "mode": "slider",
    }
    entity_id = register_entity(
        hass,
        NUMBER_DOMAIN,
        "test_name_valve_position",
        "device_0-valvePos",
        entry,
        capabilities,
        device_id=device.id,
    )
    extra_data = {
        "native_max_value": 100,
        "native_min_value": 0,
        "native_step": 1,
        "native_unit_of_measurement": "%",
        "native_value": "40",
    }
    mock_restore_cache_with_extra_data(hass, ((State(entity_id, ""), extra_data),))

    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "40"

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "50"


async def test_block_restored_number_no_last_state(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored number missing last state."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    capabilities = {
        "min": 0,
        "max": 100,
        "step": 1,
        "mode": "slider",
    }
    entity_id = register_entity(
        hass,
        NUMBER_DOMAIN,
        "test_name_valve_position",
        "device_0-valvePos",
        entry,
        capabilities,
        device_id=device.id,
    )
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "50"


async def test_block_number_set_value(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device number set value."""
    monkeypatch.setitem(
        mock_block_device.settings,
        "sleep_mode",
        {"period": 60, "unit": "m"},
    )
    await init_integration(hass, 1, sleep_period=3600)

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_block_device.reset_mock()
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_name_valve_position", ATTR_VALUE: 30},
        blocking=True,
    )
    mock_block_device.http_request.assert_called_once_with(
        "get", "thermostat/0", {"pos": 30.0}
    )


async def test_block_set_value_connection_error(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device set value connection error."""
    monkeypatch.setitem(
        mock_block_device.settings,
        "sleep_mode",
        {"period": 60, "unit": "m"},
    )
    monkeypatch.setattr(
        mock_block_device,
        "http_request",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await init_integration(hass, 1, sleep_period=3600)

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_name_valve_position", ATTR_VALUE: 30},
            blocking=True,
        )


async def test_block_set_value_auth_error(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device set value authentication error."""
    monkeypatch.setitem(
        mock_block_device.settings,
        "sleep_mode",
        {"period": 60, "unit": "m"},
    )
    monkeypatch.setattr(
        mock_block_device,
        "http_request",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1, sleep_period=3600)

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_name_valve_position", ATTR_VALUE: 30},
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
    ("name", "entity_id", "original_unit", "expected_unit", "view", "mode"),
    [
        (
            "Virtual number",
            "number.test_name_virtual_number",
            "%",
            "%",
            "field",
            NumberMode.BOX,
        ),
        (None, "number.test_name_number_203", "", None, "field", NumberMode.BOX),
        (
            "Virtual slider",
            "number.test_name_virtual_slider",
            "Hz",
            "Hz",
            "slider",
            NumberMode.SLIDER,
        ),
    ],
)
async def test_rpc_device_virtual_number(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    entity_id: str,
    original_unit: str,
    expected_unit: str | None,
    view: str,
    mode: NumberMode,
) -> None:
    """Test a virtual number for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["number:203"] = {
        "name": name,
        "min": 0,
        "max": 100,
        "meta": {"ui": {"step": 0.1, "unit": original_unit, "view": view}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["number:203"] = {"value": 12.3}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "12.3"
    assert state.attributes.get(ATTR_MIN) == 0
    assert state.attributes.get(ATTR_MAX) == 100
    assert state.attributes.get(ATTR_STEP) == 0.1
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit
    assert state.attributes.get(ATTR_MODE) is mode

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-number:203-number"

    monkeypatch.setitem(mock_rpc_device.status["number:203"], "value", 78.9)
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == "78.9"

    monkeypatch.setitem(mock_rpc_device.status["number:203"], "value", 56.7)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 56.7},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == "56.7"


async def test_rpc_remove_virtual_number_when_mode_label(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test if the virtual number will be removed if the mode has been changed to a label."""
    config = deepcopy(mock_rpc_device.config)
    config["number:200"] = {
        "name": None,
        "min": -1000,
        "max": 1000,
        "meta": {"ui": {"step": 1, "unit": "", "view": "label"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["number:200"] = {"value": 123}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        NUMBER_DOMAIN,
        "test_name_number_200",
        "number:200-number",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


async def test_rpc_remove_virtual_number_when_orphaned(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual number will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        NUMBER_DOMAIN,
        "test_name_number_200",
        "number:200-number",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry
