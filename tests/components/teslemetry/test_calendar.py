"""Test the Teslemetry calendar platform."""

from datetime import datetime
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import assert_entities, setup_platform

TZ = dt_util.get_default_time_zone()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the calendar entity is correct."""

    TZ = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2024, 1, 1, 10, 0, 0, tzinfo=TZ))

    entry = await setup_platform(hass, [Platform.CALENDAR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("entity_id"),
    [
        "calendar.energy_site_buy_tariff",
        "calendar.energy_site_sell_tariff",
    ],
)
@pytest.mark.parametrize(
    ("time"),
    [
        datetime(2024, 1, 1, 10, 0, 0, tzinfo=TZ),  # Starts Yesterday
        datetime(2024, 1, 1, 20, 0, 0, tzinfo=TZ),  # Both Today
        datetime(2024, 1, 1, 22, 0, 0, tzinfo=TZ),  # Ends Tomorrow
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_events(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    entity_id: str,
    time: datetime,
) -> None:
    """Tests that the energy tariff calendar entity events are correct."""

    freezer.move_to(time)

    await setup_platform(hass, [Platform.CALENDAR])

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes == snapshot(name="event")

    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: [entity_id],
            EVENT_START_DATETIME: dt_util.parse_datetime("2024-01-01T00:00:00Z"),
            EVENT_END_DATETIME: dt_util.parse_datetime("2024-01-07T00:00:00Z"),
        },
        blocking=True,
        return_response=True,
    )
    assert result == snapshot(name="events")
