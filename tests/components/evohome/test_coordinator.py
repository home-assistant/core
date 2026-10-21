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
from homeassistant.components.evohome.const import DOMAIN
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


async def test_setup_tolerates_failed_schedule_fetch(
    hass: HomeAssistant,
    config: dict[str, str],
) -> None:
    """Test a failed schedule fetch (a GET) is logged, not raised, so setup completes."""

    with (
        patch.object(
            Zone,
            "get_schedule",
            side_effect=evo_exc.ApiCallFailedError("API call failed"),
        ),
        patch.object(
            HotWater,
            "get_schedule",
            side_effect=evo_exc.ApiCallFailedError("API call failed"),
        ),
    ):
        async for _ in setup_evohome(hass, config, install="default"):
            assert hass.states.async_entity_ids(CLIMATE_DOMAIN)
            assert hass.states.async_entity_ids(WATER_HEATER_DOMAIN)
