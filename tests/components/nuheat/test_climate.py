"""Readback-only climate behavior and framework unit conversion."""

from asyncio import Event, create_task, sleep
from collections.abc import AsyncGenerator
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from chemelex_nuheat import (
    HoldUntilStatus,
    NuHeatApiError,
    NuHeatPermissionError,
    ScheduleMode,
    Thermostat,
    ThermostatState,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.components.nuheat.climate import NuHeatClimateEntity
from homeassistant.components.nuheat.const import (
    PRESET_PERMANENT_HOLD,
    PRESET_RUN,
    PRESET_TEMPORARY_HOLD,
    SCAN_INTERVAL,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .control_helpers import CONTROLS, advance, command
from .helpers import FakeOAuthImplementation
from .test_integration import ACCOUNT_SUBJECT, coordinator_with, oauth_data, thermostat
from .test_permanent_hold import permanent


def scheduled() -> Thermostat:
    """Return a valid scheduled sample with no contradictory hold expiry."""
    return thermostat(mode=1, hold_until=None, hold_until_status=HoldUntilStatus.NULL)


@pytest.fixture
async def mock_account(
    hass: HomeAssistant,
) -> AsyncGenerator[tuple[MockConfigEntry, AsyncMock]]:
    """Use the real setup and climate platform with mocked cloud access."""
    entry = MockConfigEntry(
        domain="nuheat", version=3, unique_id=ACCOUNT_SUBJECT, data=oauth_data()
    )
    entry.add_to_hass(hass)
    api = AsyncMock()
    api.cooldown_remaining = 0.0
    api.list_thermostats.return_value = [permanent()]
    with (
        patch(
            "homeassistant.components.nuheat.async_get_config_entry_implementation",
            return_value=FakeOAuthImplementation(),
        ),
        patch("homeassistant.components.nuheat.OAuth2Session.async_ensure_token_valid"),
        patch("homeassistant.components.nuheat.NuHeatClient", return_value=api),
    ):
        yield entry, api


@pytest.mark.parametrize(
    ("units", "current", "target", "minimum", "maximum", "requested", "native_target"),
    [
        (METRIC_SYSTEM, 21.5, 23.0, 7.0, 35.0, 24.0, 24.0),
        (US_CUSTOMARY_SYSTEM, 71.0, 73.0, 45.0, 95.0, 75.2, 24.0),
        (US_CUSTOMARY_SYSTEM, 71.0, 73.0, 45.0, 95.0, 70.0, 21.111111),
    ],
)
async def test_framework_units(
    hass: HomeAssistant,
    mock_account: tuple[MockConfigEntry, AsyncMock],
    entity_registry: er.EntityRegistry,
    units: UnitSystem,
    current: float,
    target: float,
    minimum: float,
    maximum: float,
    requested: float,
    native_target: float,
) -> None:
    """The climate service performs display-to-native conversion exactly once."""
    hass.config.units = units
    entry, api = mock_account
    assert await hass.config_entries.async_setup(entry.entry_id)
    entity_id = entity_registry.async_get_entity_id("climate", "nuheat", "ABC123")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["current_temperature"] == pytest.approx(current)
    assert state.attributes["temperature"] == pytest.approx(target)
    assert state.attributes["min_temp"] == pytest.approx(minimum)
    assert state.attributes["max_temp"] == pytest.approx(maximum)
    assert state.attributes["preset_modes"] == [
        "Run Schedule",
        "Temporary Hold",
        "Permanent Hold",
    ]
    assert state.state == HVACMode.HEAT
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": state.entity_id,
            "temperature": requested,
        },
        blocking=True,
    )
    api.set_target_temperature.assert_awaited_once_with(
        "ABC123", pytest.approx(native_target), mode=ScheduleMode.PERMANENT_HOLD
    )
    assert not hass.services.has_service("nuheat", "set_temporary_hold")
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": state.entity_id, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    api.set_standby.assert_awaited_once_with("ABC123")
    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": state.entity_id},
        blocking=True,
    )
    api.set_schedule_mode.assert_awaited_once_with("ABC123", ScheduleMode.AUTO)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_initial_entities_only(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_account: tuple[MockConfigEntry, AsyncMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Subsequent samples update availability, not the initial entity set."""
    entry, api = mock_account
    api.list_thermostats.return_value = [permanent(), thermostat("XYZ789")]
    assert await hass.config_entries.async_setup(entry.entry_id)
    original_id = entity_registry.async_get_entity_id("climate", "nuheat", "ABC123")
    missing_id = entity_registry.async_get_entity_id("climate", "nuheat", "XYZ789")
    assert original_id is not None
    assert missing_id is not None
    api.list_thermostats.return_value = [permanent(), thermostat("NEW456")]
    await advance(hass, freezer, SCAN_INTERVAL.total_seconds())
    assert entity_registry.async_get_entity_id("climate", "nuheat", "NEW456") is None
    assert hass.states.get(missing_id).state == "unavailable"
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert (
        entity_registry.async_get_entity_id("climate", "nuheat", "NEW456") is not None
    )
    assert (
        entity_registry.async_get_entity_id("climate", "nuheat", "ABC123")
        == original_id
    )
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("state", "mode", "preset"),
    [
        (ThermostatState.SCHEDULED, HVACMode.AUTO, PRESET_RUN),
        (ThermostatState.TIMED_HOLD, HVACMode.HEAT, PRESET_TEMPORARY_HOLD),
        (ThermostatState.PERMANENT_HOLD, HVACMode.HEAT, PRESET_PERMANENT_HOLD),
        (ThermostatState.MANUAL, HVACMode.HEAT, None),
        (ThermostatState.STANDBY, HVACMode.OFF, None),
    ],
)
async def test_state_mapping(
    hass: HomeAssistant, state: ThermostatState, mode: HVACMode, preset: str | None
) -> None:
    """Preserve the released hold modes without mislabeling physical Manual."""
    values = {
        ThermostatState.SCHEDULED: scheduled(),
        ThermostatState.TIMED_HOLD: thermostat(),
        ThermostatState.PERMANENT_HOLD: permanent(),
        ThermostatState.MANUAL: permanent(operating=2),
        ThermostatState.STANDBY: permanent(target=500, operating=2),
    }
    coordinator, _, _ = await coordinator_with(hass, values[state])
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    assert entity.native_temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.hvac_mode == mode
    assert entity.preset_mode == preset
    assert not entity.assumed_state
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", CONTROLS)
async def test_command_readback(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, control: str
) -> None:
    """One delayed read replaces stale data without optimism or repeated reads."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await command(entity, control)
    assert entity.native_target_temperature == 23
    assert not entity.assumed_state
    api.list_thermostats.return_value = [scheduled()]
    await advance(hass, freezer, 15)
    assert entity.hvac_mode == HVACMode.AUTO
    assert api.set_schedule_mode.await_count + api.set_standby.await_count == 1
    reads = api.list_thermostats.await_count
    await advance(hass, freezer, 30)
    assert api.list_thermostats.await_count == reads
    await coordinator.async_shutdown()


async def test_standby_and_resume(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Confirmed Standby survives recreation and exits through explicit controls."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_turn_off()
    api.set_standby.assert_awaited_once_with("ABC123")
    assert entity.hvac_mode == HVACMode.HEAT
    api.list_thermostats.return_value = [permanent(target=500, operating=2)]
    await advance(hass, freezer, 15)
    assert entity.hvac_mode == HVACMode.OFF
    assert entity.hvac_action == HVACAction.OFF
    assert entity.native_target_temperature is None
    restarted = NuHeatClimateEntity(coordinator, "ABC123")
    assert restarted.hvac_mode == HVACMode.OFF
    with pytest.raises(ServiceValidationError) as error:
        await entity.async_set_hvac_mode(HVACMode.HEAT)
    assert error.value.translation_key == "target_temperature_required"
    api.set_schedule_mode.assert_not_awaited()
    await entity.async_set_temperature(temperature=24)
    api.set_target_temperature.assert_awaited_once_with(
        "ABC123", 24, mode=ScheduleMode.PERMANENT_HOLD
    )
    await entity.async_turn_on()
    api.set_schedule_mode.assert_awaited_once_with("ABC123", ScheduleMode.AUTO)
    api.list_thermostats.return_value = [scheduled()]
    await advance(hass, freezer, 15)
    assert entity.hvac_mode == HVACMode.AUTO
    await coordinator.async_shutdown()


@pytest.mark.parametrize("raw", [None, 0, 2300])
async def test_ambiguous_manual_not_off(hass: HomeAssistant, raw: int | None) -> None:
    """Zero and missing targets cannot independently establish Standby."""
    value = replace(
        thermostat(mode=3, raw_target_temperature=raw), schedule_details_requested=True
    )
    coordinator, _, _ = await coordinator_with(hass, value)
    assert NuHeatClimateEntity(coordinator, "ABC123").hvac_mode != HVACMode.OFF
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", CONTROLS)
async def test_uncertain_write_no_retry(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, control: str
) -> None:
    """A command error never creates assumed state or triggers another write."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    api.set_schedule_mode.side_effect = NuHeatApiError("synthetic uncertain write")
    api.set_standby.side_effect = NuHeatApiError("synthetic uncertain write")
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    with pytest.raises(HomeAssistantError):
        await command(entity, control)
    assert entity.hvac_mode == HVACMode.HEAT
    assert not entity.assumed_state
    await advance(hass, freezer, 15)
    assert api.set_schedule_mode.await_count + api.set_standby.await_count == 1
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", CONTROLS)
async def test_write_ordering(hass: HomeAssistant, control: str) -> None:
    """A later mode command cannot overtake an in-flight setpoint."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    started, release = Event(), Event()

    async def write(*args: object, **kwargs: object) -> None:
        started.set()
        await release.wait()

    api.set_target_temperature.side_effect = write
    target = create_task(entity.async_set_temperature(temperature=24))
    await started.wait()
    mode = create_task(command(entity, control))
    await sleep(0)
    api.set_schedule_mode.assert_not_awaited()
    api.set_standby.assert_not_awaited()
    release.set()
    await target
    await mode
    assert api.set_schedule_mode.await_count + api.set_standby.await_count == 1
    await coordinator.async_shutdown()


async def test_unload_cancels_delayed_read(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The post-command timer does not outlive account shutdown."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    await NuHeatClimateEntity(coordinator, "ABC123").async_turn_off()
    reads = api.list_thermostats.await_count
    await coordinator.async_shutdown()
    await advance(hass, freezer, 30)
    assert api.list_thermostats.await_count == reads


@pytest.mark.parametrize("preset", [PRESET_PERMANENT_HOLD, PRESET_TEMPORARY_HOLD])
async def test_immediate_hold_keeps_successful_target(
    hass: HomeAssistant, preset: str
) -> None:
    """Mode changes reuse a successful target, never an optimistic display."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    await entity.async_set_preset_mode(preset)
    assert api.set_schedule_mode.await_args.kwargs["temperature"] == 24
    assert entity.native_target_temperature == 23
    assert not entity.assumed_state
    await coordinator.async_shutdown()


async def test_command_target_expires_without_renewal(hass: HomeAssistant) -> None:
    """Repeated Hold commands cannot keep a stale target alive indefinitely."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    with patch("homeassistant.components.nuheat.climate.monotonic") as clock:
        clock.return_value = 100
        await entity.async_set_temperature(temperature=24)
        clock.return_value = 125
        await entity.async_set_hvac_mode(HVACMode.HEAT)
        clock.return_value = 131
        with pytest.raises(ServiceValidationError):
            await entity.async_set_hvac_mode(HVACMode.HEAT)
    assert api.set_schedule_mode.await_count == 1
    await coordinator.async_shutdown()


@pytest.mark.parametrize("fresh", [False, True])
async def test_expired_target_requires_new_sample(
    hass: HomeAssistant, fresh: bool
) -> None:
    """Expiry accepts newer external targets, but not the pre-write sample."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    with patch("homeassistant.components.nuheat.climate.monotonic") as clock:
        clock.return_value = 100
        await entity.async_set_temperature(temperature=24)
        clock.return_value = 131
        if fresh:
            coordinator.async_set_updated_data({"ABC123": permanent(target=2500)})
            await entity.async_set_hvac_mode(HVACMode.HEAT)
            assert api.set_schedule_mode.await_args.kwargs["temperature"] == 25
        else:
            with pytest.raises(ServiceValidationError):
                await entity.async_set_hvac_mode(HVACMode.HEAT)
            api.set_schedule_mode.assert_not_awaited()
    await coordinator.async_shutdown()


@pytest.mark.parametrize("target", [2400, 2500])
@pytest.mark.parametrize("available", [False, True])
async def test_uncertain_target_readback(
    hass: HomeAssistant, target: int, available: bool
) -> None:
    """Only available matching newer readback resolves an uncertain setpoint."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    api.set_target_temperature.side_effect = NuHeatApiError("synthetic lost response")
    with pytest.raises(HomeAssistantError):
        await entity.async_set_temperature(temperature=25)
    with pytest.raises(ServiceValidationError):
        await entity.async_set_hvac_mode(HVACMode.HEAT)
    coordinator.async_set_updated_data({"ABC123": permanent(target=target)})
    with patch.object(coordinator, "is_thermostat_available", return_value=available):
        if available and target == 2500:
            await entity.async_set_hvac_mode(HVACMode.HEAT)
            assert api.set_schedule_mode.await_args.kwargs["temperature"] == 25
        else:
            with pytest.raises(ServiceValidationError):
                await entity.async_set_hvac_mode(HVACMode.HEAT)
            api.set_schedule_mode.assert_not_awaited()
    await coordinator.async_shutdown()


async def test_matching_readback_releases_command_target(hass: HomeAssistant) -> None:
    """After confirmation, a later external target is authoritative again."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    coordinator.async_set_updated_data({"ABC123": permanent(target=2400)})
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    coordinator.async_set_updated_data({"ABC123": permanent(target=2500)})
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    assert api.set_schedule_mode.await_args.kwargs["temperature"] == 25
    await coordinator.async_shutdown()


async def test_uncertain_temperature_blocks_implicit_target(
    hass: HomeAssistant,
) -> None:
    """An uncertain write must not fall back to an older cloud target."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    api.set_target_temperature.side_effect = NuHeatApiError("synthetic uncertainty")
    with pytest.raises(HomeAssistantError):
        await entity.async_set_temperature(temperature=25)
    with pytest.raises(ServiceValidationError):
        await entity.async_set_hvac_mode(HVACMode.HEAT)
    api.set_schedule_mode.assert_not_awaited()
    await entity.async_turn_on()
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    assert api.set_schedule_mode.await_args.kwargs["temperature"] == 23
    await coordinator.async_shutdown()


@pytest.mark.parametrize("write_applied", [False, True])
async def test_rejected_or_uncertain_target(
    hass: HomeAssistant, write_applied: bool
) -> None:
    """A definite rejection preserves the last success; uncertainty blocks reuse."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    error = NuHeatPermissionError("synthetic denial")
    error.write_applied = write_applied
    api.set_target_temperature.side_effect = error
    with pytest.raises(HomeAssistantError):
        await entity.async_set_temperature(temperature=25)
    if write_applied:
        with pytest.raises(ServiceValidationError):
            await entity.async_set_hvac_mode(HVACMode.HEAT)
        api.set_schedule_mode.assert_not_awaited()
    else:
        await entity.async_set_hvac_mode(HVACMode.HEAT)
        assert api.set_schedule_mode.await_args.kwargs["temperature"] == 24
    await coordinator.async_shutdown()


async def test_matching_sample_during_write(hass: HomeAssistant) -> None:
    """A sample arriving before the successful response can confirm the target."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    async def write(*args: object, **kwargs: object) -> None:
        coordinator.async_set_updated_data({"ABC123": permanent(target=2400)})

    api.set_target_temperature.side_effect = write
    await entity.async_set_temperature(temperature=24)
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    coordinator.async_set_updated_data({"ABC123": permanent(target=2500)})
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    assert api.set_schedule_mode.await_args.kwargs["temperature"] == 25
    await coordinator.async_shutdown()


@pytest.mark.parametrize("mode", [HVACMode.AUTO, HVACMode.OFF])
async def test_explicit_mode_clears_command_memory(
    hass: HomeAssistant, mode: HVACMode
) -> None:
    """Successful schedule and Standby commands discard the command-only target."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    await entity.async_set_hvac_mode(mode)
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    assert api.set_schedule_mode.await_args.kwargs["temperature"] == 23
    assert NuHeatClimateEntity(coordinator, "ABC123").native_target_temperature == 23
    await coordinator.async_shutdown()
