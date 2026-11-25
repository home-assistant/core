"""Tests for Shelly number platform."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, Mock

from aioshelly.const import MODEL_BLU_GATEWAY_G3, MODEL_PLUS_2PM, MODEL_WALL_DISPLAY
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest
from pytest_homeassistant.common import mock_restore_cache_with_extra_data
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_STEP,
    DOMAIN as NUMBER_DOMAIN,
    NumberMode,
    NumberService,
    NumberServiceArgument,
)
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    init_integration,
    inject_rpc_device_event,
    mutate_rpc_device_status,
    patch_platforms,
    register_device,
    register_entity,
)
from .conftest import (
    MOCK_LEDSTRIP_STATUS_BLINK,
    MOCK_LEDSTRIP_STATUS_RAINBOW,
    MOCK_LEDSTRIP_STATUS_SOLID,
)

DEVICE_BLOCK_ID = 4
LEDSTRIP_ENTITY_ID = f"{NUMBER_DOMAIN}.test_name_effect_speed"
DISPLAY_BRIGHTNESS_ENTITY_ID = f"{NUMBER_DOMAIN}.test_name_display_brightness"
MIN_AUTO_DISPLAY_BRIGHTNESS_ENTITY_ID = (
    f"{NUMBER_DOMAIN}.test_name_minimum_auto_display_brightness"
)


@pytest.fixture(autouse=True)
def fixture_platforms():
    """Limit platforms under test."""
    with patch_platforms([Platform.NUMBER]):
        yield


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

    assert (state := hass.states.get(entity_id))
    assert state.state == "50"

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "valvePos", 30)
    mock_block_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == "30"

    assert (entry := entity_registry.async_get(entity_id))
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

    assert (state := hass.states.get(entity_id))
    assert state.state == "40"

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == "50"


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

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == "50"


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
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: "number.test_name_valve_position",
            NumberServiceArgument.VALUE: 30,
        },
        blocking=True,
    )
    mock_block_device.set_thermostat_state.assert_called_once_with(0, pos=30.0)


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
        "set_thermostat_state",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await init_integration(hass, 1, sleep_period=3600)

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    with pytest.raises(
        HomeAssistantError,
        match="Device communication error occurred while calling"
        " action for number.test_name_valve_position of Test name",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            NumberService.SET_VALUE,
            {
                TargetKey.ENTITY_ID: "number.test_name_valve_position",
                NumberServiceArgument.VALUE: 30,
            },
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
        "set_thermostat_state",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1, sleep_period=3600)

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: "number.test_name_valve_position",
            NumberServiceArgument.VALUE: 30,
        },
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

    assert (state := hass.states.get(entity_id))
    assert state.state == "12.3"
    assert state.attributes.get(ATTR_MIN) == 0
    assert state.attributes.get(ATTR_MAX) == 100
    assert state.attributes.get(ATTR_STEP) == 0.1
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit
    assert state.attributes.get(ATTR_MODE) is mode

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-number:203-number_generic"

    monkeypatch.setitem(mock_rpc_device.status["number:203"], "value", 78.9)
    mock_rpc_device.mock_update()
    assert (state := hass.states.get(entity_id))
    assert state.state == "78.9"

    monkeypatch.setitem(mock_rpc_device.status["number:203"], "value", 56.7)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {TargetKey.ENTITY_ID: entity_id, NumberServiceArgument.VALUE: 56.7},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    mock_rpc_device.number_set.assert_called_once_with(203, 56.7)

    assert (state := hass.states.get(entity_id))
    assert state.state == "56.7"


async def test_rpc_virtual_number_without_view(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a virtual number without a view does not break the other ones."""
    config = deepcopy(mock_rpc_device.config)
    # Firmware 2.2.0 can send the ui settings without a view
    config["number:200"] = {
        "name": None,
        "min": 0,
        "max": 100,
        "meta": {"ui": {"step": 1, "unit": ""}},
    }
    config["number:203"] = {
        "name": None,
        "min": 0,
        "max": 100,
        "meta": {"ui": {"step": 1, "unit": "", "view": "field"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["number:200"] = {"value": 12}
    status["number:203"] = {"value": 34}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    assert "Error while setting up" not in caplog.text
    assert hass.states.get("number.test_name_number_203")
    assert hass.states.get("number.test_name_number_200") is None


@pytest.mark.usefixtures("disable_async_remove_shelly_rpc_entities")
async def test_rpc_remove_virtual_number_when_mode_label(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test virtual number removal when mode changes to label."""
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
        "number:200-number_generic",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None


async def test_rpc_remove_virtual_number_when_orphaned(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Test virtual number removal from device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        NUMBER_DOMAIN,
        "test_name_number_200",
        "number:200-number_generic",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None


async def test_blu_trv_number_entity(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test BLU TRV number entity."""
    # disable automatic temperature control in the device
    monkeypatch.setitem(mock_blu_trv.config["blutrv:200"], "enable", False)

    await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    for entity in ("external_temperature", "valve_position"):
        entity_id = f"{NUMBER_DOMAIN}.trv_name_{entity}"

        state = hass.states.get(entity_id)
        assert state == snapshot(name=f"{entity_id}-state")

        entry = entity_registry.async_get(entity_id)
        assert entry == snapshot(name=f"{entity_id}-entry")


async def test_blu_trv_ext_temp_set_value(
    hass: HomeAssistant, mock_blu_trv: Mock
) -> None:
    """Test the set value action for BLU TRV External Temperature number entity."""
    await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    entity_id = f"{NUMBER_DOMAIN}.trv_name_external_temperature"

    # After HA start the state should be unknown because there was no previous external
    # temperature report
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: entity_id,
            NumberServiceArgument.VALUE: 22.2,
        },
        blocking=True,
    )
    mock_blu_trv.mock_update()
    mock_blu_trv.blu_trv_set_external_temperature.assert_called_once_with(200, 22.2)

    assert (state := hass.states.get(entity_id))
    assert state.state == "22.2"


async def test_blu_trv_valve_pos_set_value(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the set value action for BLU TRV Valve Position number entity."""
    # disable automatic temperature control to enable valve position entity
    monkeypatch.setitem(mock_blu_trv.config["blutrv:200"], "enable", False)

    await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    entity_id = f"{NUMBER_DOMAIN}.trv_name_valve_position"

    assert (state := hass.states.get(entity_id))
    assert state.state == "0"

    monkeypatch.setitem(mock_blu_trv.status["blutrv:200"], "pos", 20)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: entity_id,
            NumberServiceArgument.VALUE: 20.0,
        },
        blocking=True,
    )
    mock_blu_trv.mock_update()
    mock_blu_trv.blu_trv_set_valve_position.assert_called_once_with(200, 20.0)

    assert (state := hass.states.get(entity_id))
    assert state.state == "20"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            DeviceConnectionError,
            "Device communication error occurred while calling action"
            " for number.trv_name_external_temperature of Test name",
        ),
        (
            RpcCallError(999),
            "RPC call error occurred while calling action"
            " for number.trv_name_external_temperature of Test name",
        ),
    ],
)
async def test_blu_trv_number_exc(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    exception: Exception,
    error: str,
) -> None:
    """Test RPC/BLU TRV number with exception."""
    await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    mock_blu_trv.blu_trv_set_external_temperature.side_effect = exception

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            NumberService.SET_VALUE,
            {
                TargetKey.ENTITY_ID: f"{NUMBER_DOMAIN}.trv_name_external_temperature",
                NumberServiceArgument.VALUE: 20.0,
            },
            blocking=True,
        )


async def test_blu_trv_number_reauth_error(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC/BLU TRV number with authentication error."""
    entry = await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    mock_blu_trv.blu_trv_set_external_temperature.side_effect = InvalidAuthError

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: f"{NUMBER_DOMAIN}.trv_name_external_temperature",
            NumberServiceArgument.VALUE: 20.0,
        },
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


async def test_cury_number_entity(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test number entities for cury component."""
    status = {
        "cury:0": {
            "id": 0,
            "slots": {
                "left": {
                    "intensity": 70,
                    "on": True,
                    "vial": {"level": 27, "name": "Forest Dream"},
                },
                "right": {
                    "intensity": 70,
                    "on": False,
                    "vial": {"level": 84, "name": "Velvet Rose"},
                },
            },
        }
    }
    monkeypatch.setattr(mock_rpc_device, "status", status)
    await init_integration(hass, 3)

    for entity in ("left_slot_intensity", "right_slot_intensity"):
        entity_id = f"{NUMBER_DOMAIN}.test_name_{entity}"

        state = hass.states.get(entity_id)
        assert state == snapshot(name=f"{entity_id}-state")

        entry = entity_registry.async_get(entity_id)
        assert entry == snapshot(name=f"{entity_id}-entry")

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: "number.test_name_left_slot_intensity",
            NumberServiceArgument.VALUE: 80.0,
        },
        blocking=True,
    )
    mock_rpc_device.mock_update()
    mock_rpc_device.cury_set.assert_called_once_with(0, slot="left", intensity=80)


@pytest.mark.parametrize(
    ("control", "ledstrip_status"),
    [
        ("speed", MOCK_LEDSTRIP_STATUS_RAINBOW),
        ("intensity", MOCK_LEDSTRIP_STATUS_BLINK),
    ],
)
async def test_rpc_ledstrip_number(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    monkeypatch: pytest.MonkeyPatch,
    control: str,
    ledstrip_status: dict[str, Any],
) -> None:
    """Test RPC LED strip effect control number."""
    entity_id = f"{NUMBER_DOMAIN}.test_name_effect_{control}"
    monkeypatch.setitem(
        mock_ledstrip_rpc_device.status, "ledstrip:0", deepcopy(ledstrip_status)
    )

    await init_integration(hass, 4)

    state = hass.states.get(entity_id)
    assert state == snapshot(name=f"{entity_id}-state")

    entry = entity_registry.async_get(entity_id)
    assert entry == snapshot(name=f"{entity_id}-entry")

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {TargetKey.ENTITY_ID: entity_id, NumberServiceArgument.VALUE: 80.0},
        blocking=True,
    )
    mock_ledstrip_rpc_device.ledstrip_set.assert_called_once_with(0, {control: 80})

    mutate_rpc_device_status(
        monkeypatch, mock_ledstrip_rpc_device, "ledstrip:0", control, 80
    )
    mock_ledstrip_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == "80"


@pytest.mark.parametrize(
    ("ledstrip_status", "expected_state"),
    [
        (MOCK_LEDSTRIP_STATUS_RAINBOW, "33"),
        (MOCK_LEDSTRIP_STATUS_SOLID, STATE_UNAVAILABLE),
        (
            MOCK_LEDSTRIP_STATUS_SOLID | {"speed": 33, "reverse": True},
            STATE_UNAVAILABLE,
        ),
        (
            {
                "id": 0,
                "on": False,
                "brightness": 36,
                "effect": "ddp",
                "speed": 33,
                "reverse": True,
            },
            STATE_UNAVAILABLE,
        ),
        (
            {
                "id": 0,
                "on": False,
                "brightness": 36,
                "effect": "rainbow",
                "reverse": True,
            },
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_rpc_ledstrip_speed_number_availability(
    hass: HomeAssistant,
    mock_ledstrip_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    ledstrip_status: dict[str, Any],
    expected_state: str,
) -> None:
    """Test RPC LED strip effect speed number availability depends on the effect."""
    monkeypatch.setitem(
        mock_ledstrip_rpc_device.status,
        "ledstrip:0",
        deepcopy(MOCK_LEDSTRIP_STATUS_SOLID),
    )

    await init_integration(hass, 4)

    assert (state := hass.states.get(LEDSTRIP_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    monkeypatch.setitem(
        mock_ledstrip_rpc_device.status, "ledstrip:0", deepcopy(ledstrip_status)
    )
    mock_ledstrip_rpc_device.mock_update()

    assert (state := hass.states.get(LEDSTRIP_ENTITY_ID))
    assert state.state == expected_state


async def test_rpc_wall_display_brightness_numbers(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC Wall Display brightness numbers."""
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2.8.5")
    monkeypatch.setitem(
        mock_rpc_device.config,
        "ui",
        {"brightness": {"auto": False, "level": 40, "min_level": 3}},
    )
    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    for entity_id in (
        DISPLAY_BRIGHTNESS_ENTITY_ID,
        MIN_AUTO_DISPLAY_BRIGHTNESS_ENTITY_ID,
    ):
        assert (state := hass.states.get(entity_id))
        assert state == snapshot(name=f"{entity_id}-state")

        assert (entry := entity_registry.async_get(entity_id))
        assert entry == snapshot(name=f"{entity_id}-entry")

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: DISPLAY_BRIGHTNESS_ENTITY_ID,
            NumberServiceArgument.VALUE: 55,
        },
        blocking=True,
    )
    mock_rpc_device.wall_display_ui_setconfig.assert_called_once_with(
        {"brightness": {"level": 55}}
    )

    mock_rpc_device.wall_display_ui_setconfig.reset_mock()
    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: MIN_AUTO_DISPLAY_BRIGHTNESS_ENTITY_ID,
            NumberServiceArgument.VALUE: 10,
        },
        blocking=True,
    )
    mock_rpc_device.wall_display_ui_setconfig.assert_called_once_with(
        {"brightness": {"min_level": 10}}
    )

    # The device ignores the level while auto brightness is on
    def _update_component_config(key: str) -> set[str]:
        mock_rpc_device.config[key]["brightness"].update(auto=True, min_level=10)
        return {"brightness"}

    mock_rpc_device.update_component_config.side_effect = _update_component_config
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "component": "ui",
                    "event": "config_changed",
                    "restart_required": False,
                    "ts": 1668522399.2,
                    "cfg_rev": 16,
                },
            ],
            "ts": 1668522399.2,
        },
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(DISPLAY_BRIGHTNESS_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get(MIN_AUTO_DISPLAY_BRIGHTNESS_ENTITY_ID))
    assert state.state == "10"


@pytest.mark.parametrize(
    ("model", "firmware", "ui_config", "has_level", "has_min_level"),
    [
        pytest.param(
            MODEL_WALL_DISPLAY,
            "2.6.2",
            {"brightness": {"auto": True, "level": 40, "min_level": 3}},
            True,
            True,
            id="min_firmware",
        ),
        pytest.param(
            MODEL_WALL_DISPLAY,
            "2.6.2",
            {"brightness": {"auto": True, "level": 40}},
            True,
            False,
            id="no_min_level",
        ),
        pytest.param(
            MODEL_WALL_DISPLAY,
            "2.6.1",
            {"brightness": {"auto": True, "level": 40, "min_level": 3}},
            False,
            False,
            id="old_firmware",
        ),
        pytest.param(
            MODEL_WALL_DISPLAY, "2.8.5", {}, False, False, id="no_brightness_config"
        ),
        pytest.param(
            MODEL_PLUS_2PM,
            "2.8.5",
            {"brightness": {"auto": True, "level": 40, "min_level": 3}},
            False,
            False,
            id="not_wall_display",
        ),
    ],
)
async def test_rpc_wall_display_brightness_numbers_supported(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    model: str,
    firmware: str,
    ui_config: dict[str, Any],
    has_level: bool,
    has_min_level: bool,
) -> None:
    """Test RPC Wall Display brightness numbers depend on model, firmware and config."""
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", firmware)
    monkeypatch.setitem(mock_rpc_device.config, "ui", ui_config)
    await init_integration(hass, 2, model=model)

    assert (hass.states.get(DISPLAY_BRIGHTNESS_ENTITY_ID) is not None) is has_level
    assert (
        hass.states.get(MIN_AUTO_DISPLAY_BRIGHTNESS_ENTITY_ID) is not None
    ) is has_min_level
