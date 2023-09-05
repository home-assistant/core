"""Tests for entity module."""

import datetime

from dateutil import tz
import pytest

from homeassistant.components.husqvarna_automower.entity import AutomowerEntity
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_entity_datetime_object(hass: HomeAssistant) -> None:
    """Test entity datetime object."""
    assert AutomowerEntity.datetime_object(None, 1685991600000) == datetime.datetime(
        2023, 6, 5, 19, 0, tzinfo=tz.gettz("US/Pacific")
    )
    assert AutomowerEntity.datetime_object(None, 0) is None
