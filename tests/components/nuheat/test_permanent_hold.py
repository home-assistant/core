"""Three-preset behavior with explicit schedule details, separate from HVAC mode."""

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestServer
from chemelex_nuheat import (
    HoldUntilStatus,
    NuHeatApiError,
    NuHeatClient,
    ScheduleMode,
    Thermostat,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.climate import HVACMode
from homeassistant.components.nuheat.climate import NuHeatClimateEntity
from homeassistant.components.nuheat.const import (
    PRESET_PERMANENT_HOLD,
    PRESET_RUN,
    PRESET_TEMPORARY_HOLD,
)
from homeassistant.components.nuheat.coordinator import NuHeatCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .test_integration import add_entity_state, coordinator_with, thermostat
from .test_setpoint_reconciliation import advance


def permanent(*, target: int = 2300, operating: int = 1) -> Thermostat:
    """Permanent."""
    return replace(
        thermostat(
            mode=3,
            raw_target_temperature=target,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        ),
        operating_mode=operating,
        schedule_mode=3,
    )


async def test_preset_menu_and_app_driven_permanent_hold(hass: HomeAssistant) -> None:
    """Preset menu and app driven permanent hold."""
    coordinator, _api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await add_entity_state(hass, entity, "climate.synthetic_hold")
    assert entity.preset_modes == [
        PRESET_RUN,
        PRESET_TEMPORARY_HOLD,
        PRESET_PERMANENT_HOLD,
    ]
    assert entity.preset_mode == PRESET_PERMANENT_HOLD
    assert entity.hvac_mode is HVACMode.AUTO
    assert entity.unique_id == "ABC123"
    assert (
        hass.states.get(entity.entity_id).attributes["preset_mode"]
        == PRESET_PERMANENT_HOLD
    )
    await entity.async_will_remove_from_hass()
    await coordinator.async_shutdown()


async def test_standby_confirmation_then_external_schedule(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Delayed Standby confirmation must not mask subsequent external changes."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_turn_off()
    assert entity.hvac_mode is HVACMode.OFF
    assert entity.assumed_state
    assert entity.native_target_temperature is None
    api.list_thermostats.return_value = [permanent(target=500, operating=2)]
    await advance(hass, freezer, 2)
    assert entity.hvac_mode is HVACMode.OFF
    assert not entity.assumed_state
    api.list_thermostats.return_value = [
        thermostat(mode=1, hold_until=None, hold_until_status=HoldUntilStatus.NULL)
    ]
    coordinator.async_schedule_reconciliation()
    await advance(hass, freezer, 2)
    assert entity.hvac_mode is HVACMode.AUTO
    assert entity.preset_mode == PRESET_RUN
    assert entity.native_target_temperature == 23
    api.set_standby.assert_awaited_once_with("ABC123")
    await coordinator.async_shutdown()


async def test_unconfirmed_standby_expires(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An unconfirmed OFF command expires without retrying the write."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_turn_off()
    assert entity.hvac_mode is HVACMode.OFF
    await advance(hass, freezer, 30)
    assert entity.hvac_mode is HVACMode.AUTO
    assert not entity.assumed_state
    api.set_standby.assert_awaited_once_with("ABC123")
    await coordinator.async_shutdown()


async def test_select_permanent_hold_preserves_target(hass: HomeAssistant) -> None:
    """Select permanent hold preserves target."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    api.list_thermostats.return_value = [permanent()]
    await entity.async_set_preset_mode(PRESET_PERMANENT_HOLD)
    api.set_schedule_mode.assert_awaited_once_with(
        "ABC123", ScheduleMode.PERMANENT_HOLD, temperature=23
    )
    assert entity.preset_mode == PRESET_PERMANENT_HOLD
    await coordinator.async_shutdown()


@pytest.mark.parametrize("imperial", [False, True])
async def test_setpoint_change_stays_permanent_and_is_optimistic(
    hass: HomeAssistant, imperial: bool
) -> None:
    """Setpoint change stays permanent and is optimistic."""
    hass.config.units = {True: US_CUSTOMARY_SYSTEM, False: METRIC_SYSTEM}[imperial]
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    requested = 75.2 if imperial else 24
    await entity.async_set_temperature(temperature=requested)
    api.set_target_temperature.assert_awaited_once_with(
        "ABC123", 24, mode=ScheduleMode.PERMANENT_HOLD
    )
    assert entity.native_target_temperature == pytest.approx(requested)
    assert entity.assumed_state
    assert entity.preset_mode == PRESET_PERMANENT_HOLD
    await coordinator.async_shutdown()


@pytest.mark.parametrize(
    ("operating", "target", "mode", "preset"),
    [
        (2, 2300, HVACMode.HEAT, None),
        (2, 500, HVACMode.OFF, None),
        (1, 500, HVACMode.AUTO, PRESET_PERMANENT_HOLD),
    ],
)
async def test_manual_and_standby_not_mislabeled(
    hass: HomeAssistant, operating: int, target: int, mode: HVACMode, preset: str | None
) -> None:
    """Manual and standby not mislabeled."""
    coordinator, _, _ = await coordinator_with(
        hass, permanent(target=target, operating=operating)
    )
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    assert entity.hvac_mode is mode
    assert entity.preset_mode == preset
    await coordinator.async_shutdown()


async def test_conflicting_or_missing_details_do_not_guess_permanent(
    hass: HomeAssistant,
) -> None:
    """Conflicting or missing details do not guess permanent."""
    value = replace(permanent(), operating_mode=None, schedule_mode=None)
    coordinator, _, _ = await coordinator_with(hass, value)
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    assert entity.preset_mode is None
    assert entity.hvac_mode is HVACMode.HEAT
    await coordinator.async_shutdown()


async def test_resume_schedule_clears_pending_target(hass: HomeAssistant) -> None:
    """Resume schedule clears pending target."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    coordinator.async_set_pending_setpoint("ABC123", 24)
    api.list_thermostats.return_value = [
        thermostat(mode=1, hold_until=None, hold_until_status=HoldUntilStatus.NULL)
    ]
    await entity.async_set_preset_mode(PRESET_RUN)
    assert coordinator.pending_setpoint("ABC123") is None
    assert entity.preset_mode == PRESET_RUN
    assert not entity.assumed_state
    await coordinator.async_shutdown()


async def test_failed_preset_write_preserves_state_and_does_not_retry(
    hass: HomeAssistant,
) -> None:
    """Failed preset write preserves state and does not retry."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    api.set_schedule_mode.side_effect = NuHeatApiError("synthetic failure")
    with pytest.raises(NuHeatApiError):
        await entity.async_set_preset_mode(PRESET_PERMANENT_HOLD)
    assert entity.preset_mode == PRESET_TEMPORARY_HOLD
    assert not entity.assumed_state
    assert api.set_schedule_mode.await_count == 1
    await coordinator.async_shutdown()


async def test_failed_post_write_read_reconciles_without_repeating_command(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Failed post write read reconciles without repeating command."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    api.set_schedule_mode.side_effect = NuHeatApiError(
        "synthetic post-PUT read failure"
    )
    with pytest.raises(NuHeatApiError):
        await entity.async_set_preset_mode(PRESET_PERMANENT_HOLD)
    assert entity.preset_mode == PRESET_TEMPORARY_HOLD
    api.list_thermostats.return_value = [permanent()]
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity.preset_mode == PRESET_PERMANENT_HOLD
    assert api.set_schedule_mode.await_count == 1
    await coordinator.async_shutdown()


async def test_permanent_from_standby_and_delayed_confirmation(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Permanent from standby and delayed confirmation."""
    coordinator, api, _ = await coordinator_with(
        hass, permanent(target=500, operating=2)
    )
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    coordinator.async_set_pending_setpoint("ABC123", 5, standby=True)
    await entity.async_set_preset_mode(PRESET_PERMANENT_HOLD)
    api.set_schedule_mode.assert_awaited_once_with(
        "ABC123", ScheduleMode.PERMANENT_HOLD, temperature=5
    )
    api.list_thermostats.return_value = [permanent(target=500)]
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity.preset_mode == PRESET_PERMANENT_HOLD
    assert entity.hvac_mode is HVACMode.AUTO
    assert entity.native_target_temperature == 5
    await coordinator.async_shutdown()


async def test_preset_reconciliation_timer_is_cancelled_on_unload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Preset reconciliation timer is cancelled on unload."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity.async_set_preset_mode(PRESET_PERMANENT_HOLD)
    reads = api.list_thermostats.await_count
    await coordinator.async_shutdown()
    freezer.tick(timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api.list_thermostats.await_count == reads


async def test_missing_schedule_details_do_not_silently_convert_hold_to_manual(
    hass: HomeAssistant,
) -> None:
    """Missing schedule details do not silently convert hold to manual."""
    value = replace(
        permanent(),
        operating_mode=None,
        schedule_mode=None,
        schedule_details_requested=True,
    )
    coordinator, api, _ = await coordinator_with(hass, value)
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    with pytest.raises(ServiceValidationError):
        await entity.async_set_temperature(temperature=24)
    api.set_target_temperature.assert_not_awaited()
    await entity.async_set_temperature(temperature=24, hvac_mode=HVACMode.HEAT)
    api.set_target_temperature.assert_awaited_once_with(
        "ABC123", 24, mode=ScheduleMode.MANUAL
    )
    await coordinator.async_shutdown()


@pytest.mark.usefixtures("socket_enabled")
async def test_real_client_and_entity_complete_four_control_roundtrip(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Real client and entity complete four control roundtrip."""
    state = {"mode": 1, "target": 2300, "operating": 1, "schedule": 1}
    writes = []

    def v2() -> dict[str, Any]:
        """V2."""
        return {
            "serialNumber": "ABC123",
            "name": "Synthetic thermostat",
            "currentTemperature": 2100,
            "online": True,
            "isHeating": False,
            "setPointTemperature": state["target"],
            "holdUntil": None,
            "mode": state["mode"],
            "errorState": None,
        }

    def v1() -> dict[str, Any]:
        """V1."""
        return {
            "serialNumber": "ABC123",
            "operatingMode": state["operating"],
            "scheduleMode": state["schedule"],
            "setPointTemp": state["target"],
            "holdSetPointDateTime": None,
            "online": True,
        }

    async def read(request: web.Request) -> web.Response:
        """Read."""
        item = v1() if "/v1/" in request.path else v2()
        return web.json_response(item if request.path.endswith("/ABC123") else [item])

    async def write(request: web.Request) -> web.Response:
        """Write."""
        body = await request.json()
        writes.append((request.path, body))
        if request.path == "/api/v1/Thermostat":
            assert set(body) == {"serialNumber", "setPointTemp", "scheduleMode"}
            assert body["scheduleMode"] == 3
            state.update(mode=3, target=body["setPointTemp"], operating=1, schedule=3)
        elif request.path.endswith("/Auto"):
            state.update(mode=1, target=2300, operating=1, schedule=1)
        elif request.path.endswith("/Hold"):
            state.update(mode=2, target=body["temperature"], operating=1, schedule=2)
        elif request.path.endswith("/Manual"):
            state.update(mode=3, target=body["temperature"], operating=2, schedule=3)
        else:
            raise AssertionError("Unexpected synthetic command")
        return web.Response(status=204)

    app = web.Application()
    for version in ("v1", "v2"):
        app.router.add_get(f"/api/{version}/Thermostat", read)
        app.router.add_get(f"/api/{version}/Thermostat/ABC123", read)
    app.router.add_put("/api/v1/Thermostat", write)
    app.router.add_put("/api/v2/Mode/{mode}", write)
    server = await aiohttp_server(app)

    async def token(_force: object) -> str:
        """Token."""
        return "synthetic-token"

    client = NuHeatClient(
        async_get_clientsession(hass),
        token,
        base_url=str(server.make_url("/")),
        include_schedule_details=True,
    )
    entry = MockConfigEntry(domain="nuheat", data={})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    coordinator = NuHeatCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await add_entity_state(hass, entity, "climate.synthetic_roundtrip")
    assert entity.preset_mode == PRESET_RUN
    await entity.async_set_preset_mode(PRESET_PERMANENT_HOLD)
    await advance(hass, freezer, 2)
    assert (
        entity.preset_mode == PRESET_PERMANENT_HOLD
        and entity.hvac_mode is HVACMode.AUTO
    )
    await entity.async_set_temperature(temperature=24)
    await advance(hass, freezer, 2)
    assert (
        entity.native_target_temperature == 24
        and entity.preset_mode == PRESET_PERMANENT_HOLD
    )
    assert writes[-1] == (
        "/api/v1/Thermostat",
        {"serialNumber": "ABC123", "setPointTemp": 2400, "scheduleMode": 3},
    )
    await entity.async_set_preset_mode(PRESET_TEMPORARY_HOLD)
    await advance(hass, freezer, 2)
    assert entity.preset_mode == PRESET_TEMPORARY_HOLD
    await entity.async_set_preset_mode(PRESET_RUN)
    await advance(hass, freezer, 2)
    assert entity.preset_mode == PRESET_RUN
    await entity.async_turn_off()
    await advance(hass, freezer, 2)
    assert entity.hvac_mode is HVACMode.OFF and entity.native_target_temperature is None
    assert state["target"] == 500
    await entity.async_turn_on()
    await advance(hass, freezer, 2)
    assert entity.hvac_mode is HVACMode.AUTO and entity.preset_mode == PRESET_RUN
    assert (
        entity.unique_id == "ABC123"
        and entity.entity_id == "climate.synthetic_roundtrip"
    )
    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
    await entity.async_will_remove_from_hass()
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", ["preset", "hvac"])
@pytest.mark.parametrize("initial", ["manual", "permanent", "standby"])
async def test_resume_schedule_reconciles_stale_immediate_response(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, control: str, initial: str
) -> None:
    """A successful Auto command must not leave stale Heat/hold until polling."""
    value = permanent(
        operating=2 if initial != "permanent" else 1,
        target=500 if initial == "standby" else 2300,
    )
    coordinator, api, _ = await coordinator_with(hass, value)
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await add_entity_state(hass, entity, "climate.synthetic_resume")
    await getattr(
        entity,
        {"preset": "async_set_preset_mode", "hvac": "async_set_hvac_mode"}[control],
    )({"preset": PRESET_RUN, "hvac": HVACMode.AUTO}[control])
    api.set_schedule_mode.assert_awaited_once_with("ABC123", ScheduleMode.AUTO)
    api.list_thermostats.return_value = [
        thermostat(
            mode=1,
            raw_target_temperature=3100,
            hold_until=None,
            hold_until_status=HoldUntilStatus.NULL,
        )
    ]
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity.hvac_mode is HVACMode.AUTO
    assert entity.preset_mode == PRESET_RUN
    assert entity.native_target_temperature == 31
    assert hass.states.get(entity.entity_id).state == HVACMode.AUTO
    assert api.set_schedule_mode.await_count == 1
    await entity.async_will_remove_from_hass()
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", ["preset", "hvac"])
async def test_failed_resume_does_not_invent_auto_or_repeat_write(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, control: str
) -> None:
    """Failed resume does not invent auto or repeat write."""
    coordinator, api, _ = await coordinator_with(hass, permanent(operating=2))
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    api.set_schedule_mode.side_effect = NuHeatApiError("synthetic uncertain write")
    with pytest.raises(NuHeatApiError):
        await getattr(
            entity,
            {"preset": "async_set_preset_mode", "hvac": "async_set_hvac_mode"}[control],
        )({"preset": PRESET_RUN, "hvac": HVACMode.AUTO}[control])
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity.hvac_mode is HVACMode.HEAT
    assert entity.native_target_temperature == 23
    assert entity.preset_mode is None
    assert api.set_schedule_mode.await_count == 1
    assert api.list_thermostats.await_count == 2
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", ["preset", "hvac"])
async def test_resume_then_permanent_reconciles_latest_command(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, control: str
) -> None:
    """Resume then permanent reconciles latest command."""
    coordinator, api, _ = await coordinator_with(hass, permanent(operating=2))
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await getattr(
        entity,
        {"preset": "async_set_preset_mode", "hvac": "async_set_hvac_mode"}[control],
    )({"preset": PRESET_RUN, "hvac": HVACMode.AUTO}[control])
    await entity.async_set_preset_mode(PRESET_PERMANENT_HOLD)
    api.list_thermostats.return_value = [permanent()]
    reads = api.list_thermostats.await_count
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity.preset_mode == PRESET_PERMANENT_HOLD
    assert api.list_thermostats.await_count == reads + 1
    assert api.set_schedule_mode.await_count == 2
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", ["preset", "hvac"])
async def test_resume_reconciliation_cancelled_on_unload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, control: str
) -> None:
    """Resume reconciliation cancelled on unload."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await getattr(
        entity,
        {"preset": "async_set_preset_mode", "hvac": "async_set_hvac_mode"}[control],
    )({"preset": PRESET_RUN, "hvac": HVACMode.AUTO}[control])
    reads = api.list_thermostats.await_count
    await coordinator.async_shutdown()
    freezer.tick(timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert api.list_thermostats.await_count == reads
