"""Tests for the LG Infrared climate platform."""

from collections.abc import Callable

from infrared_protocols.commands.lg_ac import (
    MIN_TEMP,
    LgAcCommand,
    LgAcFanSpeed,
    LgAcMode,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.lg_infrared.const import (
    FAN_MEDIUM_HIGH,
    FAN_MEDIUM_LOW,
    FAN_QUIET,
    LGDeviceType,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

_CLIMATE_ENTITY_ID = "climate.lg_ac"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.CLIMATE]


@pytest.fixture
def device_type() -> LGDeviceType:
    """Return the device type of the config entry."""
    return LGDeviceType.AC


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has an infrared receiver configured."""
    return False


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity state and registry snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_emitter(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test climate entity availability follows the infrared emitter."""
    await assert_availability_follows_source_entity(
        hass, _CLIMATE_ENTITY_ID, EMITTER_ENTITY_ID
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test setting HVAC mode to off sends power-off timings."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == LgAcCommand(mode=LgAcMode.OFF).get_raw_timings()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "temp", "fan", "expected_timings_fn"),
    [
        pytest.param(
            HVACMode.COOL,
            24,
            FAN_AUTO,
            lambda: LgAcCommand(
                mode=LgAcMode.COOL, temperature=24, fan=LgAcFanSpeed.AUTO
            ).get_raw_timings(),
            id="cool_24_auto",
        ),
        pytest.param(
            HVACMode.COOL,
            18,
            FAN_LOW,
            lambda: LgAcCommand(
                mode=LgAcMode.COOL, temperature=18, fan=LgAcFanSpeed.LOW
            ).get_raw_timings(),
            id="cool_18_low",
        ),
        pytest.param(
            HVACMode.COOL,
            30,
            FAN_HIGH,
            lambda: LgAcCommand(
                mode=LgAcMode.COOL, temperature=30, fan=LgAcFanSpeed.HIGH
            ).get_raw_timings(),
            id="cool_30_high",
        ),
        pytest.param(
            HVACMode.DRY,
            24,
            FAN_MEDIUM,
            lambda: LgAcCommand(
                mode=LgAcMode.DRY, fan=LgAcFanSpeed.MEDIUM
            ).get_raw_timings(),
            id="dry_medium",
        ),
    ],
)
async def test_set_hvac_mode_encodes_correctly(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hvac_mode: HVACMode,
    temp: int,
    fan: str,
    expected_timings_fn: Callable[[], list[int]],
) -> None:
    """Test that set_hvac_mode sends correctly encoded timings."""
    # Set initial temperature and fan before switching mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: temp},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": fan},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_timings_fn()


@pytest.mark.parametrize(
    "hvac_modes",
    [[HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY]],
)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "expected_timings_fn"),
    [
        pytest.param(
            HVACMode.HEAT,
            lambda: LgAcCommand(
                mode=LgAcMode.HEAT, temperature=MIN_TEMP, fan=LgAcFanSpeed.AUTO
            ).get_raw_timings(),
            id="heat",
        ),
        pytest.param(
            HVACMode.FAN_ONLY,
            lambda: LgAcCommand(
                mode=LgAcMode.FAN_ONLY, fan=LgAcFanSpeed.AUTO
            ).get_raw_timings(),
            id="fan_only",
        ),
    ],
)
async def test_set_hvac_mode_heat_and_fan_only(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hvac_mode: HVACMode,
    expected_timings_fn: Callable[[], list[int]],
) -> None:
    """Test heat and fan-only modes encode from the entity defaults."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_timings_fn()


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_sends_command_when_active(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_temperature sends IR when AC is on."""
    # Turn on first
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 26},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == LgAcCommand(
            mode=LgAcMode.COOL, temperature=26, fan=LgAcFanSpeed.AUTO
        ).get_raw_timings()
    )

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert float(state.attributes["temperature"]) == 26.0


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_no_command_when_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_temperature updates state but sends no IR when AC is off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 22},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert float(state.attributes["temperature"]) == 22.0


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_no_command_in_dry_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_temperature sends no IR in dry mode (protocol-fixed temp)."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.DRY},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_mode_sends_command_when_active(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_fan_mode sends IR when AC is on."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_HIGH},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == LgAcCommand(
            mode=LgAcMode.COOL, temperature=MIN_TEMP, fan=LgAcFanSpeed.HIGH
        ).get_raw_timings()
    )


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("lib_fan", "expected_fan_mode"),
    [
        pytest.param(LgAcFanSpeed.QUIET, FAN_QUIET, id="quiet"),
        pytest.param(LgAcFanSpeed.LOW, FAN_LOW, id="low"),
        pytest.param(LgAcFanSpeed.MEDIUM_LOW, FAN_MEDIUM_LOW, id="medium_low"),
        pytest.param(LgAcFanSpeed.MEDIUM, FAN_MEDIUM, id="medium"),
        pytest.param(LgAcFanSpeed.MEDIUM_HIGH, FAN_MEDIUM_HIGH, id="medium_high"),
        pytest.param(LgAcFanSpeed.HIGH, FAN_HIGH, id="high"),
        pytest.param(LgAcFanSpeed.AUTO, FAN_AUTO, id="auto"),
    ],
)
async def test_receiver_updates_state_on_cool_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    lib_fan: LgAcFanSpeed,
    expected_fan_mode: str,
) -> None:
    """Test that a received cool signal updates mode, temperature and every fan speed."""
    timings = LgAcCommand(
        mode=LgAcMode.COOL, temperature=24, fan=lib_fan
    ).get_raw_timings()

    signal = InfraredReceivedSignal(timings=timings)
    mock_infrared_receiver_entity._handle_received_signal(signal)
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes["fan_mode"] == expected_fan_mode
    assert float(state.attributes["temperature"]) == 24.0


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_updates_state_on_off_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a received off signal sets mode to off, keeping temperature and fan.

    Power-off is a fixed code carrying neither, so they must survive it.
    """
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=LgAcCommand(
                mode=LgAcMode.COOL, temperature=24, fan=LgAcFanSpeed.MEDIUM
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=LgAcCommand(mode=LgAcMode.OFF).get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes["fan_mode"] == FAN_MEDIUM
    assert float(state.attributes["temperature"]) == 24.0


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_unconfigured_hvac_mode(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a signal for a mode the user did not configure does not change state."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=LgAcCommand(
                mode=LgAcMode.HEAT, temperature=24, fan=LgAcFanSpeed.HIGH
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes["fan_mode"] == FAN_AUTO


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_non_lg_ac_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test that an unrecognised IR signal does not change state."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=[500, -500, 300, -300])
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF  # unchanged from initial


@pytest.mark.parametrize(
    ("hvac_modes", "expected_features"),
    [
        pytest.param(
            [HVACMode.COOL, HVACMode.DRY],
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE,
            id="with_temperature_mode",
        ),
        pytest.param(
            [HVACMode.DRY, HVACMode.FAN_ONLY],
            ClimateEntityFeature.FAN_MODE,
            id="without_temperature_mode",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_target_temperature_feature_follows_configured_modes(
    hass: HomeAssistant,
    expected_features: ClimateEntityFeature,
) -> None:
    """Test target temperature is only offered when a mode can carry one."""
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes["supported_features"] == expected_features
