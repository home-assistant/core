"""Test for the LCN climate platform."""

from unittest.mock import patch

from pypck.inputs import ModStatusVar, Unknown
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import Var, VarValue
from syrupy.assertion import SnapshotAssertion

# pylint: disable=hass-component-root-import
from homeassistant.components.climate import DOMAIN as DOMAIN_CLIMATE
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockConfigEntry, MockModuleConnection, MockPchkConnectionManager


async def test_setup_lcn_climate(
    hass: HomeAssistant,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the setup of climate."""
    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == snapshot(name=f"{state.entity_id}-state")


async def test_entity_state(
    hass: HomeAssistant,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test state of entity."""
    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == snapshot(
        name=f"{state.entity_id}-supported_features"
    )
    assert set(state.attributes[ATTR_HVAC_MODES]) == snapshot(
        name=f"{state.entity_id}-hvac_modes"
    )
    assert state.attributes[ATTR_MIN_TEMP] == snapshot(
        name=f"{state.entity_id}-min_temp"
    )
    assert state.attributes[ATTR_MAX_TEMP] == snapshot(
        name=f"{state.entity_id}-max_temp"
    )
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-current_temperature"
    )
    assert state.attributes[ATTR_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-temperature"
    )


async def test_entity_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the attributes of an entity."""
    entity = entity_registry.async_get("climate.climate1")

    assert entity
    assert entity.unique_id == f"{entry.entry_id}-m000007-var1.r1varsetpoint"
    assert entity.original_name == snapshot(name=f"{entity.entity_id}-original_name")


async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the hvac mode is set to heat."""
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

        assert lock_regulator.await_args.args == snapshot(
            name="lock_regulator-awaited-failed"
        )

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

        assert lock_regulator.await_args.args == snapshot(
            name="lock_regulator-awaited-success"
        )

        state = hass.states.get("climate.climate1")
        assert state is not None
        assert state.state == snapshot(name=f"{state.entity_id}-state")


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the hvac mode is set off."""
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

        assert lock_regulator.await_args.args == snapshot(
            name="lock_regulator-awaited-failed"
        )

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

        assert lock_regulator.await_args.args == snapshot(
            name="lock_regulator-awaited-success"
        )

        state = hass.states.get("climate.climate1")
        assert state is not None
        assert state.state == snapshot(name=f"{state.entity_id}-state")


async def test_set_temperature(
    hass: HomeAssistant,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the temperature is set."""
    with patch.object(MockModuleConnection, "var_abs") as var_abs:
        state = hass.states.get("climate.climate1")
        state.state = snapshot(name=f"{state.entity_id}-state")

        # wrong temperature set via service call with high/low attributes
        var_abs.return_value = False

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

        assert var_abs.await_args.args == snapshot(name="var_abs-awaited-failed")

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

        assert var_abs.await_args.args == snapshot(name="var_abs-awaited-success")

        state = hass.states.get("climate.climate1")
        assert state is not None
        assert state.attributes[ATTR_TEMPERATURE] == snapshot(
            name=f"{state.entity_id}-temperature"
        )


async def test_pushed_current_temperature_status_change(
    hass: HomeAssistant,
    entry,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the climate changes its current temperature on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    temperature = VarValue.from_celsius(25.5)

    inp = ModStatusVar(address, Var.VAR1, temperature)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == snapshot(name=f"{state.entity_id}-state")
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-current-temperature"
    )
    assert state.attributes[ATTR_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-temperature"
    )


async def test_pushed_setpoint_status_change(
    hass: HomeAssistant,
    entry,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the climate changes its setpoint on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    temperature = VarValue.from_celsius(25.5)

    inp = ModStatusVar(address, Var.R1VARSETPOINT, temperature)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == snapshot(name=f"{state.entity_id}-state")
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-current-temperature"
    )
    assert state.attributes[ATTR_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-temperature"
    )


async def test_pushed_lock_status_change(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the climate changes its setpoint on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    temperature = VarValue(0x8000)

    inp = ModStatusVar(address, Var.R1VARSETPOINT, temperature)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state is not None
    assert state.state == snapshot(name=f"{state.entity_id}-state")
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-current-temperature"
    )
    assert state.attributes[ATTR_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-temperature"
    )


async def test_pushed_wrong_input(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the climate handles wrong input correctly."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)

    await device_connection.async_process_input(Unknown("input"))
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate1")
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-current-temperature"
    )
    assert state.attributes[ATTR_TEMPERATURE] == snapshot(
        name=f"{state.entity_id}-temperature"
    )


async def test_unload_config_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the climate is removed when the config entry is unloaded."""
    await hass.config_entries.async_forward_entry_unload(entry, DOMAIN_CLIMATE)
    state = hass.states.get("climate.climate1")
    assert state.state == snapshot(name=f"{state.entity_id}-state")
