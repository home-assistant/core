"""The tests for the evohome coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from evohomeasync2 import ControlSystem, HotWater, Zone, exceptions as evo_exc
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.evohome import EvoData
from homeassistant.components.evohome.const import (
    DOMAIN,
    EVOHOME_DATA,
    SCHEDULE_MAX_AGE,
)
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import setup_evohome
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
    ("domain", "service", "service_data", "entity_fixture", "client_api"),
    [
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {},
            "ctl_id",
            "evohomeasync2.control_system.ControlSystem.set_mode",
            id="controller",
        ),
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 19.1},
            "zone_id",
            "evohomeasync2.zone.Zone.set_temperature",
            id="zone",
        ),
        pytest.param(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_ON,
            {},
            "dhw_id",
            "evohomeasync2.hotwater.HotWater.set_on",
            id="dhw",
        ),
    ],
)
@pytest.mark.usefixtures("evohome")
async def test_action_api_call_failed(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    domain: str,
    service: str,
    service_data: dict[str, float],
    entity_fixture: str,
    client_api: str,
) -> None:
    """Test an action raises HomeAssistantError if the vendor's API call fails."""

    entity_id: str = request.getfixturevalue(entity_fixture)

    with (
        patch(client_api, side_effect=evo_exc.ApiCallFailedError("API call failed")),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            domain,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == "api_call_failed"


async def test_no_schedule_fetch_at_setup(
    hass: HomeAssistant,
    config: dict[str, str],
) -> None:
    """Test no schedule is fetched during setup (only config & status are)."""

    with (
        patch.object(Zone, "get_schedule") as mock_zon,
        patch.object(HotWater, "get_schedule") as mock_dhw,
    ):
        async for _ in setup_evohome(hass, config, install="default"):
            assert hass.states.async_entity_ids(CLIMATE_DOMAIN)
            assert hass.states.async_entity_ids(WATER_HEATER_DOMAIN)

    mock_zon.assert_not_awaited()
    mock_dhw.assert_not_awaited()


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
async def test_failed_schedule_poll_keeps_entities_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    zone_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed background schedule GET is logged (and retried), not a failure."""

    update_interval = hass.data[EVOHOME_DATA].coordinator.update_interval
    assert update_interval is not None

    with patch.object(
        Zone,
        "get_schedule",
        side_effect=evo_exc.ApiCallFailedError("API call failed"),
    ) as mock_fcn:
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    mock_fcn.assert_awaited()  # the schedules were due to be fetched
    assert "Failed to update the schedule (keeping any previous one)" in caplog.text

    state = hass.states.get(zone_id)
    assert state is not None and state.state != STATE_UNAVAILABLE

    # a failed GET is retried at the next poll, rather than after SCHEDULE_MAX_AGE
    with patch.object(Zone, "get_schedule") as mock_fcn:
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    mock_fcn.assert_awaited()
