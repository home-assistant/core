"""The tests for the evohome coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from evohomeasync2 import ControlSystem, HotWater, Zone
from evohomeasync2.const import SystemMode, ZoneMode
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.evohome import EvoData
from homeassistant.components.evohome.const import DOMAIN, SCHEDULE_MAX_AGE
from homeassistant.components.evohome.coordinator import EvoDataUpdateCoordinator
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.usefixtures("evohome")
async def test_setup_platform(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities and their states after setup of evohome."""

    evo_data: EvoData = hass.data.get(DOMAIN)  # type: ignore[assignment]
    update_interval: timedelta = evo_data.coordinator.update_interval  # type: ignore[assignment]

    # confirm initial state after coordinator.async_first_refresh()...
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state != STATE_UNAVAILABLE

    with patch(
        "homeassistant.components.evohome.coordinator.EvoDataUpdateCoordinator._async_update_data",
        side_effect=UpdateFailed,
    ):
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # confirm appropriate response to loss of state...
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state == STATE_UNAVAILABLE

    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # if coordinator is working, the state will be restored
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    ("v1_tcs", "expected"),
    [
        pytest.param(
            MagicMock(get_temperatures=AsyncMock(return_value={"3432521": 19.8})),
            19.8,
            id="with_tcs",
        ),
        pytest.param(None, None, id="without_tcs"),  # zone has no v2 temperature
    ],
)
@pytest.mark.usefixtures("evohome")
async def test_high_precision_temps(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tcs: ControlSystem,
    zone_id: str,
    v1_tcs: MagicMock | None,
    expected: float | None,
) -> None:
    """Test a zone uses the v1 API's temperature, if its location has a TCS."""

    evo_data: EvoData = hass.data.get(DOMAIN)  # type: ignore[assignment]
    update_interval: timedelta = evo_data.coordinator.update_interval  # type: ignore[assignment]

    evo_data.coordinator.temps = {"3432521": 99.9}  # stale, so must be replaced

    with (
        patch("evohomeasync.EvohomeClient.get_status"),
        patch(
            "evohomeasync.EvohomeClient.location_by_id",
            new_callable=PropertyMock,
            return_value={tcs.location.id: MagicMock(tcs=v1_tcs)},
        ),
    ):
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(zone_id)
    assert state is not None
    assert state.attributes["current_temperature"] == expected


@pytest.mark.parametrize("install", TEST_INSTALLS)
@pytest.mark.usefixtures("evohome")
async def test_schedules_fetched_only_when_stale(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tcs: ControlSystem,
) -> None:
    """Test schedules are re-fetched only after SCHEDULE_MAX_AGE, not every poll."""

    evo_data: EvoData = hass.data.get(DOMAIN)  # type: ignore[assignment]
    update_interval: timedelta = evo_data.coordinator.update_interval  # type: ignore[assignment]

    num_children = len(tcs.zones) + (tcs.hotwater is not None)

    async def poll() -> None:
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    with (
        # some fixtures' statuses differ from their schedules at the frozen time
        patch.object(
            EvoDataUpdateCoordinator, "_schedule_seems_changed", return_value=False
        ),
        patch.object(Zone, "get_schedule") as mock_zon,
        patch.object(HotWater, "get_schedule") as mock_dhw,
    ):
        # the first poll after setup fetches every schedule
        await poll()
        assert mock_zon.await_count + mock_dhw.await_count == num_children

        # subsequent polls within SCHEDULE_MAX_AGE fetch none
        for _ in range(SCHEDULE_MAX_AGE // update_interval - 1):
            await poll()
        assert mock_zon.await_count + mock_dhw.await_count == num_children

        # once SCHEDULE_MAX_AGE has elapsed, every schedule is fetched again
        await poll()
        assert mock_zon.await_count + mock_dhw.await_count == num_children * 2


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    ("system_mode", "target_offset", "refetches_per_zone"),
    [
        pytest.param(SystemMode.AUTO, 1.0, 1, id="mismatch"),
        pytest.param(SystemMode.AUTO, 0.0, 0, id="match"),
        pytest.param(SystemMode.AUTO_WITH_ECO, 1.0, 0, id="mismatch_eco"),
    ],
)
@pytest.mark.usefixtures("evohome")
async def test_schedule_refetched_when_status_differs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tcs: ControlSystem,
    system_mode: SystemMode,
    target_offset: float,
    refetches_per_zone: int,
) -> None:
    """Test a schedule is re-fetched early if the status suggests it has changed.

    A mismatch that persists after the re-fetch must not cause another re-fetch.
    """

    evo_data: EvoData = hass.data.get(DOMAIN)  # type: ignore[assignment]
    update_interval: timedelta = evo_data.coordinator.update_interval  # type: ignore[assignment]

    async def poll() -> None:
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    await poll()  # the first poll after setup fetches every schedule

    # the default/ fixture's zones all have the same schedule
    this_sp = tcs.zones[0].this_switchpoint
    assert this_sp is not None
    expected_refetches = len(tcs.zones) * refetches_per_zone

    with (
        patch.object(ControlSystem, "mode", system_mode),
        patch.object(Zone, "mode", ZoneMode.FOLLOW_SCHEDULE),
        patch.object(Zone, "target_heat_temperature", this_sp[1] + target_offset),
        patch.object(Zone, "get_schedule") as mock_fcn,
    ):
        await poll()
        assert mock_fcn.await_count == expected_refetches

        await poll()
        assert mock_fcn.await_count == expected_refetches
