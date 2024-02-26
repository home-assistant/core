"""Tests for Shelly number platform."""
from unittest.mock import AsyncMock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError
import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError

from . import init_integration, register_device, register_entity

from tests.common import mock_restore_cache_with_extra_data

DEVICE_BLOCK_ID = 4


async def test_block_number_update(
    hass: HomeAssistant, mock_block_device, entity_registry, monkeypatch
) -> None:
    """Test block device number update."""
    entity_id = "number.test_name_valve_position"
    await init_integration(hass, 1, sleep_period=1000)

    assert hass.states.get(entity_id) is None

    # Make device online
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "50"

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "valvePos", 30)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == "30"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-device_0-valvePos"


async def test_block_restored_number(
    hass: HomeAssistant, mock_block_device, device_reg, monkeypatch
) -> None:
    """Test block restored number."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
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
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "50"


async def test_block_restored_number_no_last_state(
    hass: HomeAssistant, mock_block_device, device_reg, monkeypatch
) -> None:
    """Test block restored number missing last state."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
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
    )
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "50"


async def test_block_number_set_value(hass: HomeAssistant, mock_block_device) -> None:
    """Test block device number set value."""
    await init_integration(hass, 1, sleep_period=1000)

    # Make device online
    mock_block_device.mock_update()
    await hass.async_block_till_done()

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
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device set value connection error."""
    monkeypatch.setattr(
        mock_block_device,
        "http_request",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await init_integration(hass, 1, sleep_period=1000)

    # Make device online
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_name_valve_position", ATTR_VALUE: 30},
            blocking=True,
        )


async def test_block_set_value_auth_error(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device set value authentication error."""
    monkeypatch.setattr(
        mock_block_device,
        "http_request",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1, sleep_period=1000)

    # Make device online
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_name_valve_position", ATTR_VALUE: 30},
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
