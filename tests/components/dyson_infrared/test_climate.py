"""Tests for the Dyson Infrared climate platform."""

from infrared_protocols.codes.dyson.am09 import DysonAm09Code
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
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
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
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
        },
        unique_id=f"heater_cooler_{MOCK_INFRARED_ENTITY_ID}",
    )


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
        ("dyson_infrared", mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_cool_sends_cool_on_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test switching to cool mode from off powers on and sends the COOL_ON code."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [
        DysonAm09Code.ON,
        DysonAm09Code.COOL_ON,
    ]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.COOL


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_off_sends_toggle_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test switching to off sends the ON (toggle) code."""
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

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.ON]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.state == HVACMode.OFF


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_heat_sends_heat_up_and_resets_temperature(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test switching to heat mode from off powers on, sends HEAT_UP, and resets the assumed target temperature."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [
        DysonAm09Code.ON,
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
    """Test switching directly between COOL and HEAT does not resend the ON toggle."""
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
async def test_set_temperature_ignored_outside_heat_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test setting a temperature while not in heat mode sends no command."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_TEMPERATURE: 10},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_mode_speed_up(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test increasing fan_mode sends the correct number of SPEED_UP codes."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_FAN_MODE: "8"},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == (
        [DysonAm09Code.SPEED_UP] * 3
    )

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.attributes[ATTR_FAN_MODE] == "8"


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_mode_speed_down(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test decreasing fan_mode sends the correct number of SPEED_DOWN codes."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_FAN_MODE: "2"},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == (
        [DysonAm09Code.SPEED_DOWN] * 3
    )

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.attributes[ATTR_FAN_MODE] == "2"


@pytest.mark.usefixtures("init_integration")
async def test_set_swing_mode_sends_swing_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test setting swing mode sends the SWING code and updates state."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_SWING_MODE: "on"},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.SWING]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.attributes[ATTR_SWING_MODE] == "on"


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode_focused_sends_vent_thin_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test setting the focused preset sends the VENT_THIN code."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_PRESET_MODE: PRESET_FOCUSED},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.VENT_THIN]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_FOCUSED


@pytest.mark.usefixtures("init_integration")
async def test_set_preset_mode_diffused_sends_vent_wide_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    climate_entity_id: str,
) -> None:
    """Test setting the diffused preset sends the VENT_WIDE code."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: climate_entity_id, ATTR_PRESET_MODE: PRESET_DIFFUSED},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonAm09Code.VENT_WIDE]

    state = hass.states.get(climate_entity_id)
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_DIFFUSED
