"""Test Hydrawise valve."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pydrawise import APIError, NotAuthorizedError
from pydrawise.schema import Controller, Zone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hydrawise.const import (
    COMMAND_REFRESH_INTERVAL,
    COMMAND_REFRESH_TIMEOUT,
)
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_valves(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all valves are working."""
    with patch(
        "homeassistant.components.hydrawise.PLATFORMS",
        [Platform.VALVE],
    ):
        config_entry = await mock_add_config_entry()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_services(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test valve services."""
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        service_data={ATTR_ENTITY_ID: "valve.zone_one"},
        blocking=True,
    )
    mock_pydrawise.start_zone.assert_called_once_with(zones[0])
    mock_pydrawise.reset_mock()

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        service_data={ATTR_ENTITY_ID: "valve.zone_one"},
        blocking=True,
    )
    mock_pydrawise.stop_zone.assert_called_once_with(zones[0])


@pytest.mark.parametrize(
    ("service", "api_method"),
    [
        (SERVICE_OPEN_VALVE, "start_zone"),
        (SERVICE_CLOSE_VALVE, "stop_zone"),
    ],
)
@pytest.mark.usefixtures("mock_added_config_entry")
async def test_valve_api_error(
    hass: HomeAssistant,
    mock_pydrawise: AsyncMock,
    service: str,
    api_method: str,
) -> None:
    """Test that API errors raise a translated error."""
    getattr(mock_pydrawise, api_method).side_effect = APIError("Boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            VALVE_DOMAIN,
            service,
            service_data={ATTR_ENTITY_ID: "valve.zone_one"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_error"


async def _tick(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    delta: timedelta = COMMAND_REFRESH_INTERVAL,
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _open_zone_one(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        service_data={ATTR_ENTITY_ID: "valve.zone_one"},
        blocking=True,
    )


def _valve_state(hass: HomeAssistant) -> str:
    state = hass.states.get("valve.zone_one")
    assert state is not None
    return state.state


@pytest.mark.usefixtures("mock_added_config_entry")
async def test_valve_refresh_until_controller_checks_in(
    hass: HomeAssistant,
    mock_pydrawise: AsyncMock,
    controller: Controller,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the commanded state holds until the controller picks up the command."""
    refreshes = mock_pydrawise.get_user.call_count

    await _open_zone_one(hass)
    assert _valve_state(hass) == "open"

    # The controller hasn't checked in since the command, so the refresh
    # still reads the old state and the commanded state holds.
    await _tick(hass, freezer)
    assert mock_pydrawise.get_user.call_count == refreshes + 1
    assert _valve_state(hass) == "open"

    controller.last_contact_time = datetime.fromtimestamp(dt_util.utcnow().timestamp())
    await _tick(hass, freezer)
    assert mock_pydrawise.get_user.call_count == refreshes + 2

    # The controller checked in, so the reported state shows. The mocked API
    # never reports the zone as running, so that is closed.
    assert _valve_state(hass) == "closed"

    await _tick(hass, freezer)
    assert mock_pydrawise.get_user.call_count == refreshes + 2


@pytest.mark.usefixtures("mock_added_config_entry")
async def test_valve_refresh_after_command_times_out(
    hass: HomeAssistant,
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the refreshes stop when the controller never picks up a command."""
    await _open_zone_one(hass)
    refreshes = mock_pydrawise.get_user.call_count

    for _ in range(COMMAND_REFRESH_TIMEOUT // COMMAND_REFRESH_INTERVAL + 1):
        await _tick(hass, freezer)
    stopped_at = mock_pydrawise.get_user.call_count
    assert stopped_at > refreshes
    assert _valve_state(hass) == "closed"

    await _tick(hass, freezer)
    assert mock_pydrawise.get_user.call_count == stopped_at


async def test_burst_of_commands_keeps_scheduled_refresh(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a new command doesn't push back an already scheduled refresh."""
    coordinator = mock_added_config_entry.runtime_data.main

    with patch.object(coordinator, "async_request_refresh") as mock_refresh:
        await _open_zone_one(hass)
        await _tick(hass, freezer, COMMAND_REFRESH_INTERVAL - timedelta(seconds=5))
        mock_refresh.assert_not_called()

        await _open_zone_one(hass)
        await _tick(hass, freezer, timedelta(seconds=5))

    mock_refresh.assert_called_once()


async def test_command_during_refresh_keeps_one_refresh_chain(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    controller: Controller,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a command sent while a refresh runs doesn't start a second chain."""
    coordinator = mock_added_config_entry.runtime_data.main

    async def refresh_with_command() -> None:
        # Another command arrives while this refresh is still running.
        coordinator.async_refresh_after_command(controller)

    with patch.object(
        coordinator, "async_request_refresh", side_effect=refresh_with_command
    ) as mock_refresh:
        await _open_zone_one(hass)
        await _tick(hass, freezer)
        await _tick(hass, freezer)

    assert mock_refresh.call_count == 2


async def test_no_refresh_after_command_once_unloaded(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading stops the refreshes after a command."""
    coordinator = mock_added_config_entry.runtime_data.main
    await _open_zone_one(hass)
    await hass.config_entries.async_unload(mock_added_config_entry.entry_id)

    with patch.object(coordinator, "async_request_refresh") as mock_refresh:
        await _tick(hass, freezer)

    mock_refresh.assert_not_called()


async def test_refresh_after_command_stops_on_auth_failure(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the refreshes after a command stop when authentication fails."""
    await _open_zone_one(hass)
    mock_pydrawise.get_user.side_effect = NotAuthorizedError("HTTP 401")

    await _tick(hass, freezer)
    refreshes = mock_pydrawise.get_user.call_count
    assert any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in mock_added_config_entry.async_get_active_flows(
            hass, {SOURCE_REAUTH}
        )
    )

    await _tick(hass, freezer)
    assert mock_pydrawise.get_user.call_count == refreshes
