"""Test the Teslemetry calendar platform."""

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calandar(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the climate entity is correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    entry = await setup_platform(hass, [Platform.CALENDAR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    "entity_id",
    [
        "calendar.test_precondition_schedule",
        "calendar.test_charging_schedule",
        "calendar.energy_site_buy_tariff",
        "calendar.energy_site_sell_tariff",
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calandar_events(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    entity_id: str,
) -> None:
    """Tests that the climate entity is correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    await setup_platform(hass, [Platform.CALENDAR])
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
    assert result == snapshot()
