"""Test the Tessie sensor platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from tesla_fleet_api.exceptions import Forbidden, InvalidToken, MissingToken

from homeassistant.components.tessie import PLATFORMS
from homeassistant.components.tessie.const import DOMAIN
from homeassistant.components.tessie.coordinator import (
    TESSIE_ENERGY_HISTORY_INTERVAL,
    TESSIE_FLEET_API_SYNC_INTERVAL,
    TESSIE_SYNC_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .common import ERROR_AUTH, ERROR_CONNECTION, ERROR_UNKNOWN, setup_platform

from tests.common import async_fire_time_changed

WAIT = timedelta(seconds=TESSIE_SYNC_INTERVAL)


async def test_coordinator_online(
    hass: HomeAssistant, mock_get_state, freezer: FrozenDateTimeFactory
) -> None:
    """Tests that the coordinator handles online vehicles."""

    await setup_platform(hass, PLATFORMS)

    freezer.tick(WAIT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_ON


async def test_coordinator_clienterror(
    hass: HomeAssistant, mock_get_state, freezer: FrozenDateTimeFactory
) -> None:
    """Tests that the coordinator handles client errors."""

    mock_get_state.side_effect = ERROR_UNKNOWN
    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])
    coordinator = entry.runtime_data.vehicles[0].data_coordinator

    freezer.tick(WAIT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_UNAVAILABLE
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_domain == DOMAIN
    assert coordinator.last_exception.translation_key == "cannot_connect"


async def test_coordinator_auth(
    hass: HomeAssistant, mock_get_state, freezer: FrozenDateTimeFactory
) -> None:
    """Tests that the coordinator handles auth errors."""

    mock_get_state.side_effect = ERROR_AUTH
    await setup_platform(hass, [Platform.BINARY_SENSOR])

    freezer.tick(WAIT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()


async def test_coordinator_connection(
    hass: HomeAssistant, mock_get_state, freezer: FrozenDateTimeFactory
) -> None:
    """Tests that the coordinator handles connection errors."""

    mock_get_state.side_effect = ERROR_CONNECTION
    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])
    coordinator = entry.runtime_data.vehicles[0].data_coordinator
    freezer.tick(WAIT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_UNAVAILABLE
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_domain == DOMAIN
    assert coordinator.last_exception.translation_key == "cannot_connect"


async def test_coordinator_live_error(
    hass: HomeAssistant, mock_live_status, freezer: FrozenDateTimeFactory
) -> None:
    """Tests that the energy live coordinator handles fleet errors."""

    entry = await setup_platform(hass, [Platform.SENSOR])
    coordinator = entry.runtime_data.energysites[0].live_coordinator
    assert coordinator is not None

    mock_live_status.reset_mock()
    mock_live_status.side_effect = Forbidden
    freezer.tick(TESSIE_FLEET_API_SYNC_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_live_status.assert_called_once()
    assert hass.states.get("sensor.energy_site_solar_power").state == STATE_UNAVAILABLE
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_domain == DOMAIN
    assert coordinator.last_exception.translation_key == "cannot_connect"


async def test_coordinator_info_error(
    hass: HomeAssistant, mock_site_info, freezer: FrozenDateTimeFactory
) -> None:
    """Tests that the energy info coordinator handles fleet errors."""

    entry = await setup_platform(hass, [Platform.SENSOR])
    coordinator = entry.runtime_data.energysites[0].info_coordinator

    mock_site_info.reset_mock()
    mock_site_info.side_effect = Forbidden
    freezer.tick(TESSIE_FLEET_API_SYNC_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_site_info.assert_called_once()
    assert (
        hass.states.get("sensor.energy_site_vpp_backup_reserve").state
        == STATE_UNAVAILABLE
    )
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_domain == DOMAIN
    assert coordinator.last_exception.translation_key == "cannot_connect"


@pytest.mark.parametrize(
    ("mock_fixture", "side_effect"),
    [
        ("mock_live_status", InvalidToken),
        ("mock_site_info", InvalidToken),
        ("mock_site_info", MissingToken),
        ("mock_energy_history", InvalidToken),
        ("mock_energy_history", MissingToken),
    ],
)
async def test_coordinator_reauth(
    hass: HomeAssistant,
    mock_fixture: str,
    side_effect: type[Exception],
    request: pytest.FixtureRequest,
) -> None:
    """Tests that energy coordinators handle auth errors."""

    mock = request.getfixturevalue(mock_fixture)
    mock.side_effect = side_effect
    entry = await setup_platform(hass, [Platform.SENSOR])
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_energy_history_error(
    hass: HomeAssistant, mock_energy_history, freezer: FrozenDateTimeFactory
) -> None:
    """Tests that the energy history coordinator handles fleet errors."""

    entry = await setup_platform(hass, [Platform.SENSOR])
    coordinator = entry.runtime_data.energysites[0].history_coordinator
    assert coordinator is not None

    mock_energy_history.reset_mock()
    mock_energy_history.side_effect = Forbidden
    freezer.tick(TESSIE_ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_energy_history.assert_called_once()
    assert (
        hass.states.get("sensor.energy_site_grid_imported").state == STATE_UNAVAILABLE
    )
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_domain == DOMAIN
    assert coordinator.last_exception.translation_key == "cannot_connect"


async def test_coordinator_energy_history_invalid_data(
    hass: HomeAssistant, mock_energy_history, freezer: FrozenDateTimeFactory
) -> None:
    """Tests that the energy history coordinator handles invalid data."""

    entry = await setup_platform(hass, [Platform.SENSOR])
    coordinator = entry.runtime_data.energysites[0].history_coordinator
    assert coordinator is not None

    mock_energy_history.reset_mock()
    mock_energy_history.side_effect = lambda *a, **kw: {"response": {}}
    freezer.tick(TESSIE_ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_energy_history.assert_called_once()
    assert (
        hass.states.get("sensor.energy_site_grid_imported").state == STATE_UNAVAILABLE
    )
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_domain == DOMAIN
    assert coordinator.last_exception.translation_key == "invalid_energy_history_data"
