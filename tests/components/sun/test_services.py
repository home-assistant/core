"""The tests for the Sun services."""

from datetime import datetime, timedelta

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import sun
from homeassistant.components.sun.entity import ENTITY_ID
from homeassistant.components.sun.services import (
    ATTR_DURATION,
    ATTR_END_DATE_TIME,
    ATTR_INTERVAL,
    ATTR_POSITIONS,
    ATTR_START_DATE_TIME,
    SERVICE_GET_POSITIONS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

UTC_NOW = datetime(2026, 7, 4, 12, 0, 0, tzinfo=dt_util.UTC)


async def setup_sun(hass: HomeAssistant) -> None:
    """Set up the sun integration."""
    await async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {}})
    await hass.async_block_till_done()


async def get_positions(hass: HomeAssistant, data: dict) -> dict:
    """Call the get_positions service and return its response."""
    return await hass.services.async_call(
        sun.DOMAIN,
        SERVICE_GET_POSITIONS,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
        return_response=True,
    )


async def test_get_positions(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test retrieving the solar trajectory over an explicit time range."""
    with freeze_time(UTC_NOW):
        await setup_sun(hass)
        response = await get_positions(
            hass,
            {
                ATTR_START_DATE_TIME: datetime(2026, 7, 4, 6, 0, 0, tzinfo=dt_util.UTC),
                ATTR_END_DATE_TIME: datetime(2026, 7, 4, 8, 0, 0, tzinfo=dt_util.UTC),
                ATTR_INTERVAL: {"minutes": 30},
            },
        )
    assert response == snapshot


async def test_get_positions_defaults(hass: HomeAssistant) -> None:
    """Test the default range: 24 hours from now, sampled every 5 minutes."""
    with freeze_time(UTC_NOW):
        await setup_sun(hass)
        response = await get_positions(hass, {})
    positions = response[ENTITY_ID][ATTR_POSITIONS]
    assert len(positions) == 24 * 12 + 1
    assert positions[0]["datetime"] == UTC_NOW.isoformat()
    assert positions[-1]["datetime"] == (UTC_NOW + timedelta(days=1)).isoformat()
    for position in (positions[0], positions[-1]):
        assert isinstance(position["azimuth"], float)
        assert isinstance(position["elevation"], float)


async def test_get_positions_duration(hass: HomeAssistant) -> None:
    """Test the duration alternative to an explicit end time."""
    with freeze_time(UTC_NOW):
        await setup_sun(hass)
        response = await get_positions(
            hass,
            {ATTR_DURATION: {"hours": 1}, ATTR_INTERVAL: {"minutes": 15}},
        )
    positions = response[ENTITY_ID][ATTR_POSITIONS]
    assert len(positions) == 5


async def test_get_positions_end_before_start(hass: HomeAssistant) -> None:
    """Test that an inverted time range is rejected."""
    with freeze_time(UTC_NOW):
        await setup_sun(hass)
        with pytest.raises(
            ServiceValidationError,
            match="The end of the requested time range must be after its start",
        ):
            await get_positions(
                hass,
                {ATTR_END_DATE_TIME: UTC_NOW - timedelta(hours=1)},
            )


async def test_get_positions_too_many_positions(hass: HomeAssistant) -> None:
    """Test that an excessive range and interval combination is rejected."""
    with freeze_time(UTC_NOW):
        await setup_sun(hass)
        with pytest.raises(
            ServiceValidationError,
            match="Use a shorter range or a larger interval",
        ):
            await get_positions(
                hass,
                {ATTR_DURATION: {"days": 14}, ATTR_INTERVAL: {"minutes": 1}},
            )


async def test_get_positions_end_and_duration_exclusive(
    hass: HomeAssistant,
) -> None:
    """Test that an end time and a duration cannot be combined."""
    with freeze_time(UTC_NOW):
        await setup_sun(hass)
        with pytest.raises(vol.Invalid):
            await get_positions(
                hass,
                {
                    ATTR_END_DATE_TIME: UTC_NOW + timedelta(hours=1),
                    ATTR_DURATION: {"hours": 1},
                },
            )


async def test_get_positions_zero_interval(hass: HomeAssistant) -> None:
    """Test that a zero interval is rejected."""
    with freeze_time(UTC_NOW):
        await setup_sun(hass)
        with pytest.raises(vol.Invalid):
            await get_positions(hass, {ATTR_INTERVAL: {"seconds": 0}})
