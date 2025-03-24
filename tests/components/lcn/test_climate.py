"""Test for the LCN climate platform."""

from unittest.mock import patch

from pypck.inputs import ModStatusVar, Unknown
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import Var, VarUnit, VarValue
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as DOMAIN_CLIMATE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import MockConfigEntry, MockModuleConnection, init_integration

from tests.common import snapshot_platform


async def test_setup_lcn_climate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the setup of climate."""
    with patch("homeassistant.components.lcn.PLATFORMS", [Platform.CLIMATE]):
        await init_integration(hass, entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_set_hvac_mode_heat(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the hvac mode is set to heat."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "lock_regulator") as lock_regulator:
        state = hass.states.get("climate.climate1")
        state.state = HVACMode.OFF

        # command failed
        lock_regulator.return_value = False

        await hass.services.async_call(
            DOMAIN_CLIMATE,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.climate1", ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )

        lock_regulator.assert_awaited_with(0, False)

        state = hass.states.get("climate.climate1")
        assert state is not None
        assert state.state != HVACMode.HEAT

        # command success
        lock_regulator.reset_mock(return_value=True)
        lock_regulator.return_value = True

        await hass.services.async_call(
            DOMAIN_CLIMATE,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.climate1", ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )

        lock_regulator.assert_awaited_with(0, False)

        state = hass.states.get("climate.climate1")
        assert state is not None
        assert state.state == HVACMode.HEAT


async def test_set_hvac_mode_off(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the hvac mode is set off."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "lock_regulator") as lock_regulator:
        state = hass.states.get("climate.climate1")
        state.state = HVACMode.HEAT

        # command failed
        lock_regulator.return_value = False

        await hass.services.async_call(
            DOMAIN_CLIMATE,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.climate1", ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )

        lock_regulator.assert_awaited_with(0, True, -1)

        state = hass.states.get("climate.climate1")
        assert state is not None
        assert state.state != HVACMode.OFF

        # command success
        lock_regulator.reset_mock(return_value=True)
        lock_regulator.return_value = True

        await hass.services.async_call(
            DOMAIN_CLIMATE,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.climate1", ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )

        lock_regulator.assert_awaited_with(0, True, -1)

        state = hass.states.get("climate.climate1")
        assert state is not None
        assert state.state == HVACMode.OFF


async def test_set_temperature(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test the temperature is set."""
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "var_abs") as var_abs:
        state = hass.states.get("climate.climate1")
        state.state = HVACMode.HEAT

        # wrong temperature set via service call with high/low attributes
        var_abs.return_value = False

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN_CLIMATE,
                SERVICE_SET_TEMPERATURE,
                {
                    ATTR_ENTITY_ID: "climate.climate1",
                    ATTR_TARGET_TEMP_LOW: 24.5,
                    ATTR_TARGET_TEMP_HIGH: 25.5,
                },
                blocking=True,
            )

        var_abs.assert_not_awaited()

        # command failed
        var_abs.reset_mock(return_value=True)
        var_abs.return_value = False

        await hass.services.async_call(
            DOMAIN_CLIMATE,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.climate1", ATTR_TEMPERATURE: 25.5},
            blocking=True,
        )

        var_abs.assert_awaited_with(Var.R1VARSETPOINT, 25.5, VarUnit.CELSIUS)

        state = hass.states.get("climate.climate1")
        assert state is not None
        assert state.attributes[ATTR_TEMPERATURE] != 25.5

        # command success
        var_abs.reset_mock(return_value=True)
        var_abs.return_value = True

        await hass.services.async_call(
            DOMAIN_CLIMATE,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.climate1", ATTR_TEMPERATURE: 25.5},
            blocking=True,
        )

        var_abs.assert_awaited_with(Var.R1VARSETPOINT, 25.5, VarUnit.CELSIUS)

        state = hass.states.get("climate.climate1")
        assert state is not None
        assert state.attributes[ATTR_TEMPERATURE] == 25.5


async def test_pushed_current_temperature_status_change(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test the climate changes its current temperature on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    temperature = VarValue.from_celsius(25.5)

    inp = ModStatusVar(address, Var.VAR1, temperature)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 25.5
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_pushed_setpoint_status_change(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test the climate changes its setpoint on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    temperature = VarValue.from_celsius(25.5)

    inp = ModStatusVar(address, Var.R1VARSETPOINT, temperature)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_TEMPERATURE] == 25.5


async def test_pushed_lock_status_change(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test the climate changes its setpoint on status received."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    temperature = VarValue(0x8000)

    inp = ModStatusVar(address, Var.R1VARSETPOINT, temperature)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_pushed_wrong_input(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test the climate handles wrong input correctly."""
    await init_integration(hass, entry)

    device_connection = get_device_connection(hass, (0, 7, False), entry)

    await device_connection.async_process_input(Unknown("input"))
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_unload_config_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test the climate is removed when the config entry is unloaded."""
    await init_integration(hass, entry)

    await hass.config_entries.async_unload(entry.entry_id)
    state = hass.states.get("climate.climate1")
    assert state.state == STATE_UNAVAILABLE
