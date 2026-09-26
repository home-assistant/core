"""Test fans controlled by Shelly 0-10 V dimmers."""

from typing import Any
from unittest.mock import Mock

from aioshelly.const import (
    MODEL_DIMMER_10V_G3,
    MODEL_DIMMER_10V_G4,
    MODEL_PLUS_2PM,
    MODEL_PLUS_10V,
    MODEL_PLUS_10V_DIMMER,
    MODEL_PRO_DIMMER_10V_PM,
)
from aioshelly.exceptions import DeviceConnectionError, RpcCallError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import ATTR_PERCENTAGE, DOMAIN as FAN_DOMAIN
from homeassistant.components.shelly.const import (
    CONF_BLE_SCANNER_MODE,
    CONF_LIGHT_AS_FAN,
    BLEScannerMode,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, mutate_rpc_device_status

pytestmark = pytest.mark.usefixtures("mock_rpc_device")

FAN_ENTITY_ID = "fan.test_light_0"
LIGHT_ENTITY_ID = "light.test_light_0"


@pytest.mark.parametrize(
    ("model", "generation"),
    [
        pytest.param(MODEL_PLUS_10V, 2, id="plus-0-10v"),
        pytest.param(MODEL_PLUS_10V_DIMMER, 2, id="plus-0-10v-dimmer"),
        pytest.param(MODEL_PRO_DIMMER_10V_PM, 2, id="pro-0-10v-pm"),
        pytest.param(MODEL_DIMMER_10V_G3, 3, id="dimmer-0-10v-gen3"),
        pytest.param(MODEL_DIMMER_10V_G4, 4, id="dimmer-0-10v-gen4"),
    ],
)
async def test_supported_models(
    hass: HomeAssistant, model: str, generation: int
) -> None:
    """Only explicitly configured 0-10 V dimmers create fans."""
    await init_integration(
        hass, generation, model=model, options={CONF_LIGHT_AS_FAN: True}
    )
    assert hass.states.get(FAN_ENTITY_ID) is not None
    assert hass.states.get(LIGHT_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("model", "options"),
    [
        pytest.param(MODEL_DIMMER_10V_G3, {}, id="default"),
        pytest.param(MODEL_DIMMER_10V_G3, {CONF_LIGHT_AS_FAN: False}, id="disabled"),
        pytest.param(MODEL_PLUS_2PM, {CONF_LIGHT_AS_FAN: True}, id="unsupported-model"),
    ],
)
async def test_default_light(
    hass: HomeAssistant,
    model: str,
    options: dict[str, bool],
) -> None:
    """Existing lights and unsupported devices retain their original domain."""
    await init_integration(hass, 3, model=model, options=options)
    assert hass.states.get(FAN_ENTITY_ID) is None
    assert hass.states.get(LIGHT_ENTITY_ID) is not None


async def test_fan_state(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Expose the state, speed features, and original Shelly device association."""
    await init_integration(
        hass, 3, model=MODEL_DIMMER_10V_G3, options={CONF_LIGHT_AS_FAN: True}
    )
    assert hass.states.get(FAN_ENTITY_ID) == snapshot
    assert (entity := entity_registry.async_get(FAN_ENTITY_ID))
    assert entity.unique_id == "123456789ABC-light:0"
    assert entity.device_id is not None
    assert entity_registry.async_get(LIGHT_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("service", "data", "expected"),
    [
        pytest.param("turn_on", {}, {"on": True}, id="resume-speed"),
        pytest.param("turn_off", {}, {"on": False}, id="off"),
        pytest.param("turn_on", {ATTR_PERCENTAGE: 0}, {"on": False}, id="on-zero"),
        pytest.param(
            "turn_on", {ATTR_PERCENTAGE: 1}, {"on": True, "brightness": 1}, id="minimum"
        ),
        pytest.param(
            "turn_on",
            {ATTR_PERCENTAGE: 100},
            {"on": True, "brightness": 100},
            id="maximum",
        ),
        pytest.param(
            "set_percentage", {ATTR_PERCENTAGE: 0}, {"on": False}, id="speed-zero"
        ),
        pytest.param(
            "set_percentage",
            {ATTR_PERCENTAGE: 37},
            {"on": True, "brightness": 37},
            id="speed-change",
        ),
    ],
)
async def test_fan_commands(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    service: str,
    data: dict[str, int],
    expected: dict[str, bool | int],
) -> None:
    """Map fan actions to the existing Shelly light RPC without changing settings."""
    await init_integration(
        hass, 3, model=MODEL_DIMMER_10V_G3, options={CONF_LIGHT_AS_FAN: True}
    )
    mock_rpc_device.call_rpc.reset_mock()
    await hass.services.async_call(
        FAN_DOMAIN, service, {ATTR_ENTITY_ID: FAN_ENTITY_ID, **data}, blocking=True
    )
    mock_rpc_device.call_rpc.assert_called_once_with("Light.Set", {"id": 0, **expected})


@pytest.mark.parametrize(
    ("output", "brightness", "expected_state", "expected_percentage"),
    [
        pytest.param(False, 100, STATE_OFF, 0, id="off-with-remembered-speed"),
        pytest.param(True, 1, STATE_ON, 1, id="minimum-speed"),
        pytest.param(True, 37, STATE_ON, 37, id="external-speed-change"),
        pytest.param(True, 100, STATE_ON, 100, id="maximum-speed"),
    ],
)
async def test_fan_push_updates(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    output: bool,
    brightness: int,
    expected_state: str,
    expected_percentage: int,
) -> None:
    """Reflect changes made by physical inputs and other controllers."""
    await init_integration(
        hass, 3, model=MODEL_DIMMER_10V_G3, options={CONF_LIGHT_AS_FAN: True}
    )
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "light:0", "output", output)
    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "light:0", "brightness", brightness
    )
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()
    assert (state := hass.states.get(FAN_ENTITY_ID))
    assert state.state == expected_state
    assert state.attributes[ATTR_PERCENTAGE] == expected_percentage


async def test_unavailable_and_reconnect(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fan follows the shared connection availability."""
    await init_integration(
        hass, 3, model=MODEL_DIMMER_10V_G3, options={CONF_LIGHT_AS_FAN: True}
    )
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()
    assert (state := hass.states.get(FAN_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
    monkeypatch.setattr(mock_rpc_device, "connected", True)
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    await hass.async_block_till_done()
    assert (state := hass.states.get(FAN_ENTITY_ID))
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(DeviceConnectionError, id="connection-error"),
        pytest.param(RpcCallError(500), id="rpc-error"),
    ],
)
async def test_command_error(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    exception: type[Exception] | Exception,
) -> None:
    """Surface failures through the integration's existing error handling."""
    await init_integration(
        hass, 3, model=MODEL_DIMMER_10V_G3, options={CONF_LIGHT_AS_FAN: True}
    )
    mock_rpc_device.call_rpc.side_effect = exception
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN, "turn_off", {ATTR_ENTITY_ID: FAN_ENTITY_ID}, blocking=True
        )


async def test_options_change_entity_domain(
    hass: HomeAssistant, entity_registry: EntityRegistry
) -> None:
    """Changing the option reloads and replaces the previous control in both directions."""
    entry = await init_integration(hass, 3, model=MODEL_DIMMER_10V_G3)
    assert (light := entity_registry.async_get(LIGHT_ENTITY_ID))
    device_id = light.device_id
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert CONF_LIGHT_AS_FAN in result["data_schema"].schema
    options: dict[str, Any] = {
        CONF_BLE_SCANNER_MODE: BLEScannerMode.DISABLED,
        CONF_LIGHT_AS_FAN: True,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=options
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(LIGHT_ENTITY_ID) is None
    assert entity_registry.async_get(LIGHT_ENTITY_ID) is None
    assert (fan := entity_registry.async_get(FAN_ENTITY_ID))
    assert fan.device_id == device_id
    assert hass.states.get(FAN_ENTITY_ID) is not None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={**options, CONF_LIGHT_AS_FAN: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(FAN_ENTITY_ID) is None
    assert entity_registry.async_get(FAN_ENTITY_ID) is None
    assert hass.states.get(LIGHT_ENTITY_ID) is not None
    assert (light := entity_registry.async_get(LIGHT_ENTITY_ID))
    assert light.device_id == device_id


async def test_fan_option_not_offered_for_other_models(
    hass: HomeAssistant,
) -> None:
    """Regular relays and dimmers do not offer the 0-10 V fan option."""
    entry = await init_integration(hass, 2, model=MODEL_PLUS_2PM)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert CONF_LIGHT_AS_FAN not in result["data_schema"].schema
