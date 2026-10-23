"""Every write reconciles; explicit timed holds use the existing entity safely."""

from asyncio import Event, create_task, sleep
from datetime import UTC, datetime, timedelta
import logging
from math import inf, nan
from pathlib import Path

from chemelex_nuheat import HoldUntilStatus, NuHeatApiError, ScheduleMode
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
import yaml

from homeassistant.components.climate import HVACMode
from homeassistant.components.nuheat import climate
from homeassistant.components.nuheat.climate import NuHeatClimateEntity
from homeassistant.components.nuheat.const import (
    PRESET_PERMANENT_HOLD,
    PRESET_RUN,
    PRESET_TEMPORARY_HOLD,
    SCAN_INTERVAL,
)
from homeassistant.components.nuheat.services import async_setup_services
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .test_integration import coordinator_with, thermostat
from .test_permanent_hold import permanent
from .test_setpoint_reconciliation import advance

CONTROLS = ["run", "temporary", "permanent", "heat", "auto", "off", "on"]


@pytest.mark.parametrize("control", CONTROLS)
async def test_mode_commands_wait_for_inflight_setpoint(
    hass: HomeAssistant, control: str
) -> None:
    """A slow earlier setpoint cannot finish after a newer mode command."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    started = Event()
    release = Event()

    async def write(*_args: object, **_kwargs: object) -> None:
        started.set()
        await release.wait()

    api.set_target_temperature.side_effect = write
    setpoint = create_task(entity.async_set_temperature(temperature=24))
    await started.wait()
    mode = create_task(command(entity, control))
    try:
        await sleep(0)
        api.set_schedule_mode.assert_not_awaited()
        api.set_standby.assert_not_awaited()
    finally:
        release.set()
        await setpoint
        await mode
        await coordinator.async_shutdown()
    assert api.set_schedule_mode.await_count + api.set_standby.await_count == 1


@pytest.mark.parametrize("control", ["temporary", "permanent", "heat"])
async def test_mode_change_preserves_accepted_target_before_readback(
    hass: HomeAssistant, control: str
) -> None:
    """Switching mode must not reuse a stale cloud target."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    await command(entity, control)
    assert api.set_schedule_mode.await_args.kwargs["temperature"] == 24
    await coordinator.async_shutdown()


async def command(entity: NuHeatClimateEntity, control: str) -> None:
    """Command."""
    if control in ("run", "temporary", "permanent"):
        await entity.async_set_preset_mode(
            {
                "run": PRESET_RUN,
                "temporary": PRESET_TEMPORARY_HOLD,
                "permanent": PRESET_PERMANENT_HOLD,
            }[control]
        )
    elif control in ("heat", "auto"):
        await entity.async_set_hvac_mode(
            HVACMode.HEAT if control == "heat" else HVACMode.AUTO
        )
    elif control == "off":
        await entity.async_turn_off()
    else:
        await entity.async_turn_on()


@pytest.mark.parametrize("control", CONTROLS)
async def test_all_controls_refresh_after_stale_read(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, control: str
) -> None:
    """All controls refresh after stale read."""
    coordinator, api, _ = await coordinator_with(hass, permanent(operating=2))
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await command(entity, control)
    fresh = {
        "run": thermostat(
            mode=1,
            raw_target_temperature=3100,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        ),
        "temporary": thermostat(),
        "permanent": permanent(),
        "heat": permanent(operating=2),
        "off": permanent(operating=2, target=500),
    }
    api.list_thermostats.return_value = [fresh.get(control, fresh["run"])]
    reads = api.list_thermostats.await_count
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api.list_thermostats.await_count == reads + 1
    assert entity.thermostat == api.list_thermostats.return_value[0]
    assert api.set_schedule_mode.await_count + api.set_standby.await_count == 1
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", CONTROLS)
async def test_all_controls_failed_writes_read_without_retry(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, control: str
) -> None:
    """All controls failed writes read without retry."""
    coordinator, api, _ = await coordinator_with(hass, permanent(operating=2))
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    api.set_schedule_mode.side_effect = NuHeatApiError("synthetic uncertain write")
    api.set_standby.side_effect = NuHeatApiError("synthetic uncertain write")
    with pytest.raises(NuHeatApiError):
        await command(entity, control)
    reads = api.list_thermostats.await_count
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api.list_thermostats.await_count == reads + 1
    assert entity.hvac_mode is HVACMode.HEAT
    assert entity.preset_mode is None
    assert not entity.assumed_state
    assert api.set_schedule_mode.await_count + api.set_standby.await_count == 1
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", CONTROLS)
async def test_all_controls_coalesce_and_cancel_on_unload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, control: str
) -> None:
    """All controls coalesce and cancel on unload."""
    coordinator, api, _ = await coordinator_with(hass, permanent(operating=2))
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await command(entity, control)
    await command(entity, control)
    reads = api.list_thermostats.await_count
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api.list_thermostats.await_count == reads + 1
    await command(entity, control)
    reads = api.list_thermostats.await_count
    await coordinator.async_shutdown()
    freezer.tick(timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api.list_thermostats.await_count == reads


@pytest.mark.parametrize("imperial", [False, True])
async def test_real_action_dispatch_units_local_timezone_and_expiry_preserved(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, imperial: bool
) -> None:
    """Real action dispatch units local timezone and expiry preserved."""
    freezer.move_to("2026-10-22T20:00:00+00:00")
    await hass.config.async_set_time_zone("America/New_York")
    hass.config.units = {True: US_CUSTOMARY_SYSTEM, False: METRIC_SYSTEM}[imperial]
    coordinator, api, _ = await coordinator_with(hass, permanent())
    platform = EntityPlatform(
        hass=hass,
        logger=logging.getLogger(__name__),
        domain="climate",
        platform_name="nuheat",
        platform=None,
        scan_interval=SCAN_INTERVAL,
        entity_namespace=None,
    )
    async_setup_services(hass)
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await platform.async_add_entities([entity])
    original_id = entity.entity_id
    expected = datetime(2026, 10, 23, 0, 30, tzinfo=UTC)
    await hass.services.async_call(
        "nuheat",
        "set_temporary_hold",
        {
            "entity_id": original_id,
            "temperature": 75.2 if imperial else 24,
            "hold_until": "2026-10-22T20:30:00",
        },
        blocking=True,
    )
    api.set_target_temperature.assert_awaited_once_with(
        "ABC123", 24, mode=ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE, hold_until=expected
    )
    assert entity.assumed_state
    assert entity.native_target_temperature == pytest.approx(75.2 if imperial else 24)
    api.list_thermostats.return_value = [
        thermostat(raw_target_temperature=2400, hold_until=expected)
    ]
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity.preset_mode == PRESET_TEMPORARY_HOLD
    assert not entity.assumed_state
    await entity.async_set_temperature(temperature=77 if imperial else 25)
    assert api.set_target_temperature.await_args.kwargs["hold_until"] == expected
    assert entity.entity_id == original_id and entity.unique_id == "ABC123"
    await platform.async_reset()
    await coordinator.async_shutdown()


@pytest.mark.parametrize(
    "until",
    [
        datetime(2020, 1, 1),
        datetime(2020, 1, 1, tzinfo=UTC),
        datetime(2027, 3, 14, 2, 30),
        datetime(2026, 11, 1, 1, 30),
    ],
)
async def test_invalid_or_dst_ambiguous_expiry_never_writes(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, until: datetime
) -> None:
    """Invalid or dst ambiguous expiry never writes."""
    freezer.move_to("2026-10-22T20:00:00+00:00")
    await hass.config.async_set_time_zone("America/New_York")
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    entity.hass = hass
    with pytest.raises(ServiceValidationError):
        await entity.async_set_temporary_hold(24, until)
    api.set_target_temperature.assert_not_awaited()
    await coordinator.async_shutdown()


@pytest.mark.parametrize("temperature", [nan, inf, 6, 36])
async def test_invalid_timed_hold_target_never_writes(
    hass: HomeAssistant, temperature: float
) -> None:
    """Invalid timed hold target never writes."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    entity.hass = hass
    with pytest.raises(ServiceValidationError):
        await entity.async_set_temporary_hold(
            temperature, dt_util.utcnow() + timedelta(hours=1)
        )
    api.set_target_temperature.assert_not_awaited()
    await coordinator.async_shutdown()


async def test_explicit_dst_offset_and_failed_write(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Explicit dst offset and failed write."""
    freezer.move_to("2026-10-22T20:00:00+00:00")
    await hass.config.async_set_time_zone("America/New_York")
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    entity.hass = hass
    api.set_target_temperature.side_effect = NuHeatApiError("synthetic failure")
    until = datetime.fromisoformat("2026-11-01T01:30:00-04:00")
    with pytest.raises(NuHeatApiError):
        await entity.async_set_temporary_hold(24, until)
    assert api.set_target_temperature.await_args.kwargs["hold_until"] == datetime(
        2026, 11, 1, 5, 30, tzinfo=UTC
    )
    assert not entity.assumed_state
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api.set_target_temperature.await_count == 1
    await coordinator.async_shutdown()


async def test_rapid_target_change_preserves_new_expiry_before_cloud_confirmation(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Rapid target change preserves new expiry before cloud confirmation."""
    freezer.move_to("2026-10-22T20:00:00+00:00")
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    entity.hass = hass
    until = datetime(2026, 10, 23, 0, 30, tzinfo=UTC)
    await entity.async_set_temporary_hold(24, until)
    api.list_thermostats.return_value = [permanent(target=2400)]
    await advance(hass, freezer, 2)
    assert coordinator.pending_hold_until("ABC123") == until
    await entity.async_set_temperature(temperature=25)
    api.set_target_temperature.assert_awaited_with(
        "ABC123", 25, mode=ScheduleMode.HOLD_UNTIL_NEXT_SCHEDULE, hold_until=until
    )
    await entity.async_set_preset_mode(PRESET_RUN)
    assert coordinator.pending_hold_until("ABC123") is None
    await coordinator.async_shutdown()


async def test_unconfirmed_timed_hold_expires_and_unload_cancels_timers(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Unconfirmed timed hold expires and unload cancels timers."""
    freezer.move_to("2026-10-22T20:00:00+00:00")
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    entity.hass = hass
    until = datetime(2026, 10, 23, 0, 30, tzinfo=UTC)
    await entity.async_set_temporary_hold(24, until)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.pending_hold_until("ABC123") is None
    assert not entity.assumed_state
    await entity.async_set_temporary_hold(24, until)
    reads = api.list_thermostats.await_count
    await coordinator.async_shutdown()
    freezer.tick(timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api.list_thermostats.await_count == reads


async def test_action_form_selectors_are_valid() -> None:
    """Action form selectors are valid."""
    data = yaml.safe_load(
        Path(climate.__file__).with_name("services.yaml").read_text(encoding="utf-8")
    )
    fields = data["set_temporary_hold"]["fields"]
    assert set(fields) == {"temperature", "hold_until"}
    for field in fields.values():
        selector.validate_selector(field["selector"])


async def test_action_registered_without_available_accounts(
    hass: HomeAssistant,
) -> None:
    """The action remains available before an account loads successfully."""
    assert await async_setup_component(hass, "nuheat", {})
    assert hass.services.has_service("nuheat", "set_temporary_hold")
