"""Test Hydrawise valve."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pydrawise import APIError
from pydrawise.schema import Controller, Zone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hydrawise.const import (
    COMMAND_REFRESH_INTERVAL,
    COMMAND_REFRESH_TIMEOUT,
)
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
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


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(COMMAND_REFRESH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_added_config_entry")
async def test_valve_refresh_until_controller_checks_in(
    hass: HomeAssistant,
    mock_pydrawise: AsyncMock,
    controller: Controller,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test refreshing after a command until the controller picks it up."""
    refreshes = mock_pydrawise.get_user.call_count

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        service_data={ATTR_ENTITY_ID: "valve.zone_one"},
        blocking=True,
    )
    state = hass.states.get("valve.zone_one")
    assert state is not None
    assert state.state == "open"

    # The controller hasn't checked in since the command, so keep refreshing.
    await _tick(hass, freezer)
    assert mock_pydrawise.get_user.call_count == refreshes + 1

    controller.last_contact_time = datetime.fromtimestamp(dt_util.utcnow().timestamp())
    await _tick(hass, freezer)
    assert mock_pydrawise.get_user.call_count == refreshes + 2

    # It has checked in now, so the refreshes stop.
    await _tick(hass, freezer)
    assert mock_pydrawise.get_user.call_count == refreshes + 2

    # The mocked API never reports the zone as running, so the refreshes put
    # the valve back to closed.
    state = hass.states.get("valve.zone_one")
    assert state is not None
    assert state.state == "closed"


@pytest.mark.usefixtures("mock_added_config_entry")
async def test_valve_refresh_after_command_times_out(
    hass: HomeAssistant,
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the refreshes stop when the controller never picks up a command."""
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        service_data={ATTR_ENTITY_ID: "valve.zone_one"},
        blocking=True,
    )
    refreshes = mock_pydrawise.get_user.call_count

    for _ in range(COMMAND_REFRESH_TIMEOUT // COMMAND_REFRESH_INTERVAL + 1):
        await _tick(hass, freezer)
    stopped_at = mock_pydrawise.get_user.call_count
    assert stopped_at > refreshes

    await _tick(hass, freezer)
    assert mock_pydrawise.get_user.call_count == stopped_at
