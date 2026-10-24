"""Exercise eventual consistency with synthetic commands and controlled time."""

from asyncio import Event, create_task, sleep
from datetime import timedelta

from chemelex_nuheat import NuHeatApiError, NuHeatAuthError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.climate import HVACMode
from homeassistant.components.nuheat.climate import NuHeatClimateEntity
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .test_integration import add_entity_state, coordinator_with, thermostat


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Run scheduled callbacks without sleeping or contacting a service."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(("imperial", "requested"), [(False, 24), (True, 75.2)])
async def test_stale_readback_then_delayed_confirmation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    imperial: bool,
    requested: float,
) -> None:
    """Stale data cannot bounce the target back; the two-second read confirms it."""
    if imperial:
        hass.config.units = US_CUSTOMARY_SYSTEM
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await add_entity_state(hass, entity, "climate.reconcile")
    api.set_target_temperature.return_value = None
    await entity.async_set_temperature(temperature=requested)
    assert entity.native_target_temperature == pytest.approx(requested)
    assert hass.states.get(entity.entity_id).attributes[
        ATTR_TEMPERATURE
    ] == pytest.approx(round(requested) if imperial else requested)
    assert entity.assumed_state
    assert coordinator.data["ABC123"].target_temperature == 23
    assert api.list_thermostats.await_count == 2
    api.list_thermostats.return_value = [thermostat(raw_target_temperature=2400)]
    await advance(hass, freezer, 2)
    assert api.list_thermostats.await_count == 3
    assert entity.native_target_temperature == pytest.approx(requested)
    assert not entity.assumed_state
    await advance(hass, freezer, 40)
    assert api.list_thermostats.await_count == 3
    await entity.async_will_remove_from_hass()
    await coordinator.async_shutdown()


async def test_stale_reads_expire_and_stop_retrying(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Optimism is bounded even if NuHeat never reports the requested target."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await add_entity_state(hass, entity, "climate.reconcile")
    await entity.async_set_temperature(temperature=24)
    for seconds in (2, 8, 8, 8):
        await advance(hass, freezer, seconds)
        assert entity.native_target_temperature == 24
    await advance(hass, freezer, 4)
    assert entity.native_target_temperature == 23
    assert not entity.assumed_state
    assert "not confirmed" in caplog.text
    reads = api.list_thermostats.await_count
    await advance(hass, freezer, 30)
    assert api.list_thermostats.await_count == reads
    await entity.async_will_remove_from_hass()
    await coordinator.async_shutdown()


async def test_failed_write_does_not_assume_success_or_retry_write(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A rejected write or failed post-PUT GET only schedules a later read."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    api.set_target_temperature.side_effect = NuHeatApiError("synthetic failure")
    with pytest.raises(NuHeatApiError):
        await entity.async_set_temperature(temperature=24)
    assert entity.native_target_temperature == 23
    assert not entity.assumed_state
    api.list_thermostats.return_value = [thermostat(raw_target_temperature=2400)]
    await advance(hass, freezer, 2)
    assert entity.native_target_temperature == 24
    assert api.set_target_temperature.await_count == 1
    assert api.list_thermostats.await_count == 2
    await coordinator.async_shutdown()


async def test_rapid_commands_coalesce_and_use_newest_target(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Each successful command replaces its timer and the previous target."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    await advance(hass, freezer, 1)
    await entity.async_set_temperature(temperature=25)
    await advance(hass, freezer, 1)
    assert api.list_thermostats.await_count == 2
    assert entity.native_target_temperature == 25
    api.list_thermostats.return_value = [thermostat(raw_target_temperature=2500)]
    await advance(hass, freezer, 1)
    assert api.list_thermostats.await_count == 3
    assert not entity.assumed_state
    await advance(hass, freezer, 30)
    assert entity.native_target_temperature == 25
    await coordinator.async_shutdown()


async def test_concurrent_commands_are_serialized(hass: HomeAssistant) -> None:
    """A slow older write cannot finish after the newer write."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    started, release = Event(), Event()

    async def write(*args, **kwargs):
        started.set()
        await release.wait()

    api.set_target_temperature.side_effect = write
    first = create_task(entity.async_set_temperature(temperature=24))
    await started.wait()
    second = create_task(entity.async_set_temperature(temperature=25))
    release.set()
    await first
    await second
    assert [call.args[1] for call in api.set_target_temperature.await_args_list] == [
        24,
        25,
    ]
    assert entity.native_target_temperature == 25
    await coordinator.async_shutdown()


async def test_inflight_old_read_cannot_confirm_new_request(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A GET begun before a write cannot confirm the newer command."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    coordinator.async_set_pending_setpoint("ABC123", 24)
    started, release = Event(), Event()

    async def read():
        started.set()
        await release.wait()
        return [thermostat(raw_target_temperature=2500)]

    api.list_thermostats.side_effect = read
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await started.wait()
    coordinator.async_set_pending_setpoint("ABC123", 25)
    release.set()
    await hass.async_block_till_done()
    assert coordinator.pending_setpoint("ABC123") == 25
    await coordinator.async_shutdown()


@pytest.mark.parametrize("error", [NuHeatApiError, NuHeatAuthError])
async def test_refresh_errors_do_not_leave_permanent_optimism(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    error: type[NuHeatApiError | NuHeatAuthError],
) -> None:
    """Transport and authentication failures retain normal availability semantics."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    api.list_thermostats.side_effect = error("synthetic read failure")
    await advance(hass, freezer, 2)
    assert not coordinator.last_update_success
    await advance(hass, freezer, 28)
    assert entity.native_target_temperature == 23
    assert not entity.assumed_state
    await coordinator.async_shutdown()


async def test_unload_cancels_reconcile_and_expiry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unloading leaves no delayed reads or timeout callbacks behind."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    await NuHeatClimateEntity(coordinator, "ABC123").async_set_temperature(
        temperature=24
    )
    reads = api.list_thermostats.await_count
    await coordinator.async_shutdown()
    await advance(hass, freezer, 60)
    assert api.list_thermostats.await_count == reads
    assert coordinator.pending_setpoint("ABC123") is None
    assert "not confirmed" not in caplog.text


async def test_timeout_is_independent_of_slow_refresh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An in-flight cloud request cannot keep the optimistic target forever."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    started, release = Event(), Event()

    async def read():
        started.set()
        await release.wait()
        return [thermostat()]

    api.list_thermostats.side_effect = read
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await started.wait()
    try:
        freezer.tick(timedelta(seconds=28))
        async_fire_time_changed(hass)
        await sleep(0)
        assert not entity.assumed_state
        assert entity.native_target_temperature == 23
    finally:
        release.set()
        await hass.async_block_till_done()
        await coordinator.async_shutdown()


async def test_pending_devices_have_independent_deadlines(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A second thermostat command cannot prolong the first thermostat's target."""
    coordinator, _api, _ = await coordinator_with(
        hass, thermostat(), thermostat("XYZ789")
    )
    first = NuHeatClimateEntity(coordinator, "ABC123")
    second = NuHeatClimateEntity(coordinator, "XYZ789")
    await first.async_set_temperature(temperature=24)
    await advance(hass, freezer, 20)
    await second.async_set_temperature(temperature=25)
    await advance(hass, freezer, 10)
    assert not first.assumed_state
    assert first.target_temperature == 23
    assert second.assumed_state
    assert second.target_temperature == 25
    await coordinator.async_shutdown()


@pytest.mark.parametrize("command", ["off", "auto", "preset"])
async def test_other_commands_supersede_pending_target(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, command: str
) -> None:
    """Mode commands must not leave an earlier optimistic setpoint active."""
    coordinator, _api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_temperature(temperature=24)
    if command == "off":
        await entity.async_turn_off()
    elif command == "auto":
        await entity.async_set_hvac_mode(HVACMode.AUTO)
    else:
        await entity.async_set_preset_mode("run_schedule")
    assert coordinator.pending_setpoint("ABC123") is None
    await advance(hass, freezer, 40)
    await coordinator.async_shutdown()
