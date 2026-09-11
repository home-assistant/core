"""Tests for the Dyson Infrared climate platform."""

from typing import Any

from infrared_protocols.codes.dyson.am09 import DysonAm09Code
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_OFF,
    SWING_ON,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.dyson_infrared.climate import (
    PRESET_DIFFUSED,
    PRESET_FOCUSED,
)
from homeassistant.components.dyson_infrared.const import (
    CONF_COMMAND_STEP_DELAY,
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    DysonDeviceType,
    DysonTemperatureUnit,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_TEMPERATURE_UNIT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import (
    MockConfigEntry,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from tests.components.infrared import EMITTER_ENTITY_ID as MOCK_INFRARED_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for a heater/cooler device."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000002",
        title="Dyson Heater/Cooler via Test IR emitter",
        data={
            CONF_DEVICE_TYPE: DysonDeviceType.HEATER_COOLER,
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
            CONF_COMMAND_STEP_DELAY: 0,
            CONF_TEMPERATURE_UNIT: DysonTemperatureUnit.CELSIUS,
        },
        unique_id=f"heater_cooler_{MOCK_INFRARED_ENTITY_ID}",
    )


CLIMATE_ENTITY_ID = (
    "climate.dyson_heater_cooler_via_test_ir_emitter_dyson_heater_cooler"
)


@pytest.mark.parametrize("hvac_mode", [HVACMode.COOL, HVACMode.OFF])
@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_rejects_non_heat_hvac_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
    hvac_mode: HVACMode,
) -> None:
    """Test a target temperature combined with a non-heat mode is rejected outright."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: climate_entity_id,
                ATTR_TEMPERATURE: 5,
                ATTR_HVAC_MODE: hvac_mode,
            },
            blocking=True,
        )

    # Rejected before anything is sent, so the unit is left heating as it was.
    assert not mock_infrared_emitter_entity.send_command_calls
    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.HEAT


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_applies_heat_hvac_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test passing heat alongside a target temperature still steps the target.

    Only reachable from heat, since set_temperature is not offered in any other
    mode, so the mode itself is already correct and just needs to not interfere.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: climate_entity_id,
            ATTR_TEMPERATURE: 3,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == (
        [DysonAm09Code.HEAT_UP] * 2
    )

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 3


@pytest.mark.usefixtures("mock_make_dyson_am09_command")
async def test_restores_last_active_mode_after_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test an off unit that was last heating still gets a mode select when cooled."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(CLIMATE_ENTITY_ID, HVACMode.OFF),
                {
                    "last_active_mode": HVACMode.HEAT.value,
                    "temperature_unit": UnitOfTemperature.CELSIUS,
                    "target_temperature": 12.0,
                    "fan_mode": "8",
                    "preset_mode": PRESET_FOCUSED,
                    "swing_mode": SWING_ON,
                },
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    # Without the restored mode this would assume cool and send POWER alone,
    # physically resuming heat while reporting cool.
    assert mock_infrared_emitter_entity.send_command_calls == [
        DysonAm09Code.POWER,
        DysonAm09Code.COOL_ON,
    ]


@pytest.mark.usefixtures("mock_make_dyson_am09_command")
async def test_restores_values_hidden_while_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test the adjustable values come back even though they are hidden while off."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(CLIMATE_ENTITY_ID, HVACMode.OFF),
                {
                    "last_active_mode": HVACMode.COOL.value,
                    "temperature_unit": UnitOfTemperature.CELSIUS,
                    "target_temperature": 12.0,
                    "fan_mode": "8",
                    "preset_mode": PRESET_FOCUSED,
                    "swing_mode": SWING_ON,
                },
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_FAN_MODE] == "8"
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_FOCUSED
    assert state.attributes[ATTR_SWING_MODE] == SWING_ON
    assert state.attributes[ATTR_TEMPERATURE] == 12.0


@pytest.mark.parametrize(
    "extra_data",
    [
        pytest.param({"last_active_mode": HVACMode.HEAT.value}, id="incomplete"),
        pytest.param(
            {
                "last_active_mode": HVACMode.HEAT.value,
                "temperature_unit": UnitOfTemperature.CELSIUS,
                "target_temperature": "not-a-number",
                "fan_mode": "8",
                "preset_mode": PRESET_FOCUSED,
                "swing_mode": SWING_ON,
            },
            id="unparsable",
        ),
    ],
)
@pytest.mark.usefixtures("mock_make_dyson_am09_command")
async def test_unusable_restored_extra_data_falls_back_to_defaults(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    extra_data: dict[str, Any],
) -> None:
    """Test extra data that cannot be read is discarded rather than partly applied."""
    mock_restore_cache_with_extra_data(
        hass, [(State(CLIMATE_ENTITY_ID, HVACMode.OFF), extra_data)]
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_FAN_MODE] == "5"
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_DIFFUSED
    assert state.attributes[ATTR_SWING_MODE] == SWING_OFF


@pytest.mark.usefixtures("mock_make_dyson_am09_command")
async def test_restores_hvac_mode_without_extra_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test a state stored without extra data still restores the visible mode."""
    mock_restore_cache(hass, [State(CLIMATE_ENTITY_ID, HVACMode.COOL)])
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state
    assert state.state == HVACMode.COOL


@pytest.mark.parametrize(
    ("restored_mode", "requested_mode", "expected_code"),
    [
        pytest.param(HVACMode.HEAT, HVACMode.COOL, DysonAm09Code.COOL_ON, id="heat"),
        pytest.param(HVACMode.COOL, HVACMode.HEAT, DysonAm09Code.HEAT_UP, id="cool"),
    ],
)
@pytest.mark.usefixtures("mock_make_dyson_am09_command")
async def test_restored_running_mode_still_gets_a_mode_select(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    restored_mode: HVACMode,
    requested_mode: HVACMode,
    expected_code: DysonAm09Code,
) -> None:
    """Test a running unit restored without extra data is not assumed to be cooling."""
    mock_restore_cache(hass, [State(CLIMATE_ENTITY_ID, restored_mode)])
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID, ATTR_HVAC_MODE: requested_mode},
        blocking=True,
    )

    # Taking the default cooling assumption here would send nothing at all,
    # leaving the unit in its old mode while the entity reports the new one.
    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state
    assert state.state == requested_mode


@pytest.mark.usefixtures("mock_make_dyson_am09_command")
async def test_state_survives_a_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test the values the entity stores on removal are the ones it reads back."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for service, service_data in (
        (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.HEAT}),
        (SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "9"}),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_FOCUSED}),
        (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 7}),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: CLIMATE_ENTITY_ID} | service_data,
            blocking=True,
        )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(CLIMATE_ENTITY_ID)
    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_FAN_MODE] == "9"
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_FOCUSED
    assert state.attributes[ATTR_TEMPERATURE] == 7


@pytest.fixture
async def running_climate_entity_id(
    hass: HomeAssistant,
    climate_entity_id: str,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> str:
    """Return the climate entity id with the unit already switched on."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()
    return climate_entity_id


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        pytest.param(SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "8"}, id="fan_mode"),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_FOCUSED},
            id="preset_mode",
        ),
        pytest.param(SERVICE_SET_SWING_MODE, {ATTR_SWING_MODE: "on"}, id="swing_mode"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_adjustments_raise_while_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
    service: str,
    service_data: dict[str, str],
) -> None:
    """Test adjustments are rejected while off, since the unit only accepts power."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: climate_entity_id} | service_data,
            blocking=True,
        )

    assert not mock_infrared_emitter_entity.send_command_calls


@pytest.mark.usefixtures("init_integration")
async def test_supported_features_follow_hvac_mode(
    hass: HomeAssistant,
    climate_entity_id: str,
) -> None:
    """Test adjustments are advertised only while running, and target temp only in heat."""
    adjustments = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
    )

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == ClimateEntityFeature(0)

    for hvac_mode, expected in (
        (HVACMode.COOL, adjustments),
        (HVACMode.HEAT, adjustments | ClimateEntityFeature.TARGET_TEMPERATURE),
        (HVACMode.OFF, ClimateEntityFeature(0)),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: hvac_mode},
            blocking=True,
        )
        state = hass.states.get(climate_entity_id)
        assert state
        assert state.attributes[ATTR_SUPPORTED_FEATURES] == expected


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the climate entity is created with correct attributes and attached to a device."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_cool_from_off_only_powers_on(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test switching to cool from off only powers on, since standby resumes cool."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.POWER]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.COOL


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_off_sends_toggle_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test switching to off sends the POWER (toggle) code."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.POWER]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.OFF


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_cool_after_power_cycle_does_not_switch_to_heat(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test returning to cool after a power cycle does not toggle the unit into heat."""
    for hvac_mode in (HVACMode.COOL, HVACMode.OFF):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: hvac_mode},
            blocking=True,
        )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    # COOL_ON toggles cool/heat, so resending it here would land the unit in heat.
    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.POWER]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.COOL


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_same_value_sends_no_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test reselecting the current mode sends nothing, since COOL_ON would toggle it."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    assert not mock_infrared_emitter_entity.send_command_calls

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.COOL


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_cool_after_heat_power_cycle_selects_cool(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test returning to cool after a heat power cycle still sends the mode select."""
    for hvac_mode in (HVACMode.HEAT, HVACMode.OFF):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: hvac_mode},
            blocking=True,
        )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [
        DysonAm09Code.POWER,
        DysonAm09Code.COOL_ON,
    ]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.COOL


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_heat_leaves_temperature_unchanged(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test switching to heat mode powers on and selects heat without touching the target."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [
        DysonAm09Code.POWER,
        DysonAm09Code.HEAT_UP,
    ]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 1


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_between_cool_and_heat_does_not_repower(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test switching directly between COOL and HEAT does not resend the POWER toggle or compensate the target temperature."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.HEAT_UP]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.HEAT


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_steps_heat_up(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test raising the target temperature sends the correct number of HEAT_UP codes."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_TEMPERATURE: 4},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == (
        [DysonAm09Code.HEAT_UP] * 3
    )

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] == 4


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_rounds_fractional_value(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test a fractional target (e.g. from a Fahrenheit-converted request) rounds to the nearest degree instead of truncating down."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_TEMPERATURE: 3.6},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == (
        [DysonAm09Code.HEAT_UP] * 3
    )

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] == 4


@pytest.mark.usefixtures("mock_make_dyson_am09_command")
async def test_fahrenheit_device_uses_fahrenheit_range_and_single_steps(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a Fahrenheit device exposes the Fahrenheit range and sends one command per degree."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000003",
        title="Dyson Heater/Cooler via Test IR emitter",
        data={
            CONF_DEVICE_TYPE: DysonDeviceType.HEATER_COOLER,
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
            CONF_COMMAND_STEP_DELAY: 0,
            CONF_TEMPERATURE_UNIT: DysonTemperatureUnit.FAHRENHEIT,
        },
        unique_id=f"heater_cooler_fahrenheit_{MOCK_INFRARED_ENTITY_ID}",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = er.async_entries_for_config_entry(entity_registry, entry.entry_id)[
        0
    ].entity_id

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_MIN_TEMP] == 34
    assert state.attributes[ATTR_MAX_TEMP] == 99

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 35},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.HEAT_UP]

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] == 35


@pytest.mark.usefixtures("mock_make_dyson_am09_command")
async def test_fahrenheit_device_rounds_converted_celsius_request(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a Celsius request onto a Fahrenheit device rounds to the nearest degree.

    The system unit is left metric while the device is in Fahrenheit, so the
    service converts the target and hands over a fractional value.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000004",
        title="Dyson Heater/Cooler via Test IR emitter",
        data={
            CONF_DEVICE_TYPE: DysonDeviceType.HEATER_COOLER,
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
            CONF_COMMAND_STEP_DELAY: 0,
            CONF_TEMPERATURE_UNIT: DysonTemperatureUnit.FAHRENHEIT,
        },
        unique_id=f"heater_cooler_converted_{MOCK_INFRARED_ENTITY_ID}",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = er.async_entries_for_config_entry(entity_registry, entry.entry_id)[
        0
    ].entity_id

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    # 2 degrees Celsius converts to 35.6 F, two steps up from the 34 F minimum
    # the entity starts at. Truncating instead of rounding would send only one.
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 2},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == (
        [DysonAm09Code.HEAT_UP] * 2
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_raises_outside_heat_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test setting a temperature while off is rejected since it isn't supported."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: climate_entity_id, ATTR_TEMPERATURE: 10},
            blocking=True,
        )

    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_raises_in_cool_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test setting a temperature while cooling is rejected since the AM09 has no cool setpoint."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: climate_entity_id, ATTR_TEMPERATURE: 10},
            blocking=True,
        )

    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_heat_retains_temperature_across_power_cycle(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test turning heat off and back on keeps the previous target temperature."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_TEMPERATURE: 5},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.POWER]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] == 5


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_mode_speed_up(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    running_climate_entity_id: str,
) -> None:
    """Test increasing fan_mode sends the correct number of SPEED_UP codes."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: running_climate_entity_id, ATTR_FAN_MODE: "8"},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == (
        [DysonAm09Code.SPEED_UP] * 3
    )

    state = hass.states.get(running_climate_entity_id)
    assert state
    assert state.attributes[ATTR_FAN_MODE] == "8"


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_mode_speed_down(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    running_climate_entity_id: str,
) -> None:
    """Test decreasing fan_mode sends the correct number of SPEED_DOWN codes."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: running_climate_entity_id, ATTR_FAN_MODE: "2"},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == (
        [DysonAm09Code.SPEED_DOWN] * 3
    )

    state = hass.states.get(running_climate_entity_id)
    assert state
    assert state.attributes[ATTR_FAN_MODE] == "2"


@pytest.mark.usefixtures("init_integration")
async def test_set_swing_mode_sends_swing_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    running_climate_entity_id: str,
) -> None:
    """Test setting swing mode sends the SWING code and updates state."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: running_climate_entity_id, ATTR_SWING_MODE: "on"},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.SWING]

    state = hass.states.get(running_climate_entity_id)
    assert state
    assert state.attributes[ATTR_SWING_MODE] == "on"


@pytest.mark.usefixtures("init_integration")
async def test_set_swing_mode_unchanged_sends_no_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    running_climate_entity_id: str,
) -> None:
    """Test setting swing mode to its current value sends no command, since SWING is a toggle."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: running_climate_entity_id, ATTR_SWING_MODE: "off"},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode_focused_sends_vent_thin_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    running_climate_entity_id: str,
) -> None:
    """Test setting the focused preset sends the VENT_THIN code."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: running_climate_entity_id, ATTR_PRESET_MODE: PRESET_FOCUSED},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.VENT_THIN]

    state = hass.states.get(running_climate_entity_id)
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_FOCUSED


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode_diffused_sends_vent_wide_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    running_climate_entity_id: str,
) -> None:
    """Test setting the diffused preset sends the VENT_WIDE code."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: running_climate_entity_id, ATTR_PRESET_MODE: PRESET_FOCUSED},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: running_climate_entity_id, ATTR_PRESET_MODE: PRESET_DIFFUSED},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.VENT_WIDE]

    state = hass.states.get(running_climate_entity_id)
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_DIFFUSED


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode_unchanged_sends_no_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    running_climate_entity_id: str,
) -> None:
    """Test setting the preset to its current value sends no command."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: running_climate_entity_id, ATTR_PRESET_MODE: PRESET_DIFFUSED},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == []
