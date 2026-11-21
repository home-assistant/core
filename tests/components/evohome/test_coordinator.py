"""The tests for the evohome coordinator."""

from contextlib import AbstractContextManager
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import evohomeasync as ec1
from evohomeasync2 import ControlSystem, HotWater, Zone, exceptions as evo_exc
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateService,
    ClimateServiceArgument,
)
from homeassistant.components.evohome.const import (
    EVOHOME_DATA,
    SCAN_INTERVAL_DEFAULT,
    SCHEDULE_MAX_AGE,
)
from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    WaterHeaterService,
)
from homeassistant.const import CONF_SCAN_INTERVAL, STATE_UNAVAILABLE, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    UpdateFailed,
    UpdateFailedUnreachable,
)

from .conftest import setup_evohome
from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.usefixtures("evohome")
async def test_setup_platform(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities and their states after setup of evohome."""

    # confirm initial state after coordinator.async_first_refresh()...
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state != STATE_UNAVAILABLE

    with patch(
        "evohomeasync2.location.Location.get_status",
        side_effect=evo_exc.ApiCallFailedError("API call failed"),
    ):
        freezer.tick(SCAN_INTERVAL_DEFAULT)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # confirm appropriate response to loss of state...
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state == STATE_UNAVAILABLE

    freezer.tick(SCAN_INTERVAL_DEFAULT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # if coordinator is working, the state will be restored
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state != STATE_UNAVAILABLE


def _v1_location_by_id(
    *temps: dict[str, float],
) -> AbstractContextManager[PropertyMock]:
    """Patch the v1 client's locations, each with a TCS that has these temps."""

    return patch(
        "evohomeasync.EvohomeClient.location_by_id",
        new_callable=PropertyMock,
        return_value={
            f"loc_{idx}": MagicMock(
                tcs=MagicMock(get_temperatures=AsyncMock(return_value=t))
            )
            for idx, t in enumerate(temps)
        },
    )


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance time by one scan interval, so the coordinators refresh."""

    freezer.tick(SCAN_INTERVAL_DEFAULT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


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

    with (
        patch("evohomeasync.EvohomeClient.get_status"),
        _v1_location_by_id({"3432521": 99.9}),
    ):
        await _poll(hass, freezer)

    state = hass.states.get(zone_id)
    assert state is not None
    assert state.attributes["current_temperature"] == 99.9  # stale, so must be replaced

    with (
        patch("evohomeasync.EvohomeClient.get_status"),
        patch(
            "evohomeasync.EvohomeClient.location_by_id",
            new_callable=PropertyMock,
            return_value={tcs.location.id: MagicMock(tcs=v1_tcs)},
        ),
    ):
        await _poll(hass, freezer)

    state = hass.states.get(zone_id)
    assert state is not None
    assert state.attributes["current_temperature"] == expected


async def test_update_intervals(
    hass: HomeAssistant,
    config: ConfigType,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test scan_interval applies to the location and to high-precision temps."""

    config[CONF_SCAN_INTERVAL] = 600

    async for _ in setup_evohome(hass, config, install="default"):
        with (
            patch("evohomeasync2.location.Location.get_status") as mock_v2,
            patch("evohomeasync.EvohomeClient.get_status") as mock_v1,
            _v1_location_by_id(),
        ):
            await _poll(hass, freezer)  # 300 seconds

            mock_v2.assert_not_awaited()
            mock_v1.assert_not_awaited()

            await _poll(hass, freezer)  # 600 seconds

            mock_v2.assert_awaited_once_with()
            mock_v1.assert_awaited_once_with()


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
async def test_high_precision_temps_multiple_locations(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    zone_id: str,
) -> None:
    """Test high-precision temps from all of an account's locations are retained."""

    # the zone's temp is from the first location, so a later one must not drop it
    with (
        patch("evohomeasync.EvohomeClient.get_status"),
        _v1_location_by_id({"3432521": 19.8}, {"9999999": 21.3}),
    ):
        await _poll(hass, freezer)

    state = hass.states.get(zone_id)
    assert state is not None
    assert state.attributes["current_temperature"] == 19.8


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ec1.ApiCallFailedError("API call failed"), id="api_error"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
@pytest.mark.usefixtures("evohome")
async def test_high_precision_temps_failed_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    zone_id: str,
    exception: Exception,
) -> None:
    """Test a failed v1 poll drops the high-precision temps, rather than keep them."""

    with (
        patch("evohomeasync.EvohomeClient.get_status"),
        _v1_location_by_id({"3432521": 99.9}),
    ):
        await _poll(hass, freezer)

    state = hass.states.get(zone_id)
    assert state is not None
    assert state.attributes["current_temperature"] == 99.9

    with patch("evohomeasync.EvohomeClient.get_status", side_effect=exception):
        await _poll(hass, freezer)

    assert "They will be ignored this refresh cycle" in caplog.text

    # the zone falls back to its v2 temperature (it has none in this fixture)
    state = hass.states.get(zone_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes["current_temperature"] is None


@pytest.mark.parametrize("install", TEST_INSTALLS)
@pytest.mark.usefixtures("evohome")
async def test_schedules_fetched_only_when_stale(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tcs: ControlSystem,
) -> None:
    """Test schedules are re-fetched only after SCHEDULE_MAX_AGE, not every poll."""

    update_interval = SCAN_INTERVAL_DEFAULT

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
            ClimateService.TURN_OFF,
            {},
            "ctl_id",
            "evohomeasync2.control_system.ControlSystem.set_mode",
            id="controller",
        ),
        pytest.param(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {ClimateServiceArgument.TEMPERATURE: 19.1},
            "zone_id",
            "evohomeasync2.zone.Zone.set_temperature",
            id="zone",
        ),
        pytest.param(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.TURN_ON,
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
            {TargetKey.ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == "api_request_failed"


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    ("reason", "translation_key"),
    [
        pytest.param(
            evo_exc.ApiCallErrorReason.CALL_FAILED,
            "api_request_failed",
            id="call_failed",
        ),
        pytest.param(
            evo_exc.ApiCallErrorReason.CONNECTION_FAILED,
            "api_connection_failed",
            id="connection_failed",
        ),
        pytest.param(
            evo_exc.ApiCallErrorReason.CREDENTIALS_INVALID,
            "api_credentials_invalid",
            id="credentials_invalid",
        ),
        pytest.param(
            evo_exc.ApiCallErrorReason.RATE_LIMITED,
            "api_rate_limited",
            id="rate_limited",
        ),
        pytest.param(
            evo_exc.ApiCallErrorReason.REQUEST_REJECTED,
            "api_request_rejected",
            id="request_rejected",
        ),
        pytest.param(
            evo_exc.ApiCallErrorReason.SERVER_ERROR,
            "api_server_error",
            id="server_error",
        ),
        pytest.param(
            evo_exc.ApiCallErrorReason.RESPONSE_NOT_JSON,
            "api_request_failed",
            id="fallback",
        ),
    ],
)
@pytest.mark.usefixtures("evohome")
async def test_action_api_call_failed_reason(
    hass: HomeAssistant,
    zone_id: str,
    reason: evo_exc.ApiCallErrorReason,
    translation_key: str,
) -> None:
    """Test the translation key of a failed action depends on the error's reason."""

    with (
        patch(
            "evohomeasync2.zone.Zone.set_temperature",
            side_effect=evo_exc.ApiCallFailedError("API call failed", reason=reason),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {TargetKey.ENTITY_ID: zone_id, ClimateServiceArgument.TEMPERATURE: 19.1},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.parametrize(
    ("exception", "error_type", "translation_key", "retry_after"),
    [
        pytest.param(
            evo_exc.ApiConnectionFailedError("API call failed"),
            UpdateFailedUnreachable,
            "api_connection_failed",
            None,
            id="connection_failed",
        ),
        pytest.param(
            evo_exc.ApiRateLimitExceededError("Rate limit exceeded", retry_after=900),
            UpdateFailed,
            "api_rate_limited",
            900,
            id="rate_limited",
        ),
        pytest.param(
            evo_exc.ApiCallFailedError(
                "API call failed",
                reason=evo_exc.ApiCallErrorReason.SERVER_ERROR,
            ),
            UpdateFailed,
            "api_server_error",
            None,
            id="server_error",
        ),
        pytest.param(
            evo_exc.ApiCallFailedError(
                "API call failed",
                status=503,
                reason=evo_exc.ApiCallErrorReason.SERVER_ERROR,
                retry_after=120,
            ),
            UpdateFailed,
            "api_server_error",
            120,
            id="server_error_retry_after",
        ),
    ],
)
@pytest.mark.usefixtures("evohome")
async def test_poll_api_call_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    exception: evo_exc.ApiCallFailedError,
    error_type: type[UpdateFailed],
    translation_key: str,
    retry_after: float | None,
) -> None:
    """Test a failed poll of a location raises UpdateFailed, by the error's reason."""

    coordinator = hass.data[EVOHOME_DATA].coordinator

    with patch("evohomeasync2.location.Location.get_status", side_effect=exception):
        freezer.tick(SCAN_INTERVAL_DEFAULT)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert type(coordinator.last_exception) is error_type
    assert coordinator.last_exception.translation_key == translation_key
    assert coordinator.last_exception.retry_after == retry_after


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
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(evo_exc.ApiCallFailedError("API call failed"), id="call_failed"),
        pytest.param(
            evo_exc.BadUserCredentialsError("Authentication failed"),
            id="authentication_failed",
        ),
    ],
)
async def test_failed_schedule_poll_keeps_entities_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    zone_id: str,
    caplog: pytest.LogCaptureFixture,
    exception: evo_exc.ApiCallFailedError,
) -> None:
    """Test a failed background schedule GET is logged (and retried), not a failure."""

    coordinator = hass.data[EVOHOME_DATA].coordinator
    update_interval = SCAN_INTERVAL_DEFAULT

    with patch.object(Zone, "get_schedule", side_effect=exception) as mock_fcn:
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    mock_fcn.assert_awaited()  # the schedules were due to be fetched
    assert "Failed to update the schedule (keeping any previous one)" in caplog.text
    assert "Unexpected error fetching" not in caplog.text
    assert coordinator.last_update_success

    state = hass.states.get(zone_id)
    assert state is not None and state.state != STATE_UNAVAILABLE

    # a failed GET is retried at the next poll, rather than after SCHEDULE_MAX_AGE
    with patch.object(Zone, "get_schedule") as mock_fcn:
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    mock_fcn.assert_awaited()
