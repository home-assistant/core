"""Tests for the Tankerkoenig services."""

from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tankerkoenig.const import (
    DOMAIN,
    SERVICE_GET_OPENING_TIMES,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import STATION

from tests.common import MockConfigEntry

ENTITY_ID = "binary_sensor.station_somewhere_street_1_status"


@pytest.mark.usefixtures("setup_integration")
async def test_get_opening_times(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the opening times of a station are returned."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_OPENING_TIMES,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("whole_day", "expected"),
    [
        (
            True,
            [{"days": "Mo-So", "start_time": "00:00:00", "end_time": "23:59:59"}],
        ),
        (False, []),
    ],
)
async def test_get_opening_times_without_list(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
    whole_day: bool,
    expected: list[dict[str, str]],
) -> None:
    """Test a station without a list of opening times."""
    tankerkoenig.station_details.return_value = replace(
        STATION, whole_day=whole_day, opening_times=[]
    )
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_OPENING_TIMES,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == {ENTITY_ID: {"opening_times": expected}}
