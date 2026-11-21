"""Tests for the Starlink sensors."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.starlink.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, PERCENTAGE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .patchers import (
    HISTORY_STATS_SUCCESS_PATCHER,
    LOCATION_DATA_SUCCESS_PATCHER,
    SLEEP_DATA_SUCCESS_PATCHER,
    STATUS_DATA_FIXTURE,
    STATUS_DATA_TARGET,
)

ENTITY_ID = "sensor.starlink_signal_quality"


async def setup_integration(
    hass: HomeAssistant, status_data: JsonArrayType
) -> MockConfigEntry:
    """Set up the Starlink integration with the given status data."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4:0000"})

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
        patch(STATUS_DATA_TARGET, return_value=status_data),
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


@pytest.mark.parametrize(
    ("signal_quality", "expected_state"),
    [
        pytest.param(0.7, "70.0", id="reported"),
        pytest.param(None, STATE_UNKNOWN, id="not_reported"),
    ],
)
async def test_signal_quality(
    hass: HomeAssistant, signal_quality: float | None, expected_state: str
) -> None:
    """Test the signal quality sensor."""
    status_data = deepcopy(STATUS_DATA_FIXTURE)
    status_data[0]["signal_quality"] = signal_quality

    await setup_integration(hass, status_data)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
