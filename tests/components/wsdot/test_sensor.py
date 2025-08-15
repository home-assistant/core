"""The tests for the WSDOT platform."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.wsdot.const import CONF_TRAVEL_TIMES, DOMAIN
from homeassistant.components.wsdot.sensor import SCAN_INTERVAL
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_PLATFORM,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

TRAVEL_TIME_SUBENTRY = {
    "subentry_type": "travel_time",
    "title": "I-90 EB",
    "data": {
        CONF_ID: 96,
        CONF_NAME: "Seattle-Bellevue via I-90 (EB AM)",
    },
}


@pytest.mark.parametrize(
    "subentries",
    [
        [TRAVEL_TIME_SUBENTRY],
    ],
    ids=[""],
)
async def test_travel_sensor_details(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the wsdot Travel Time sensor details."""
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    state = hass.states.get("sensor.seattle_bellevue_via_i_90_eb_am")
    assert state is not None
    assert state.name == "Seattle-Bellevue via I-90 (EB AM)"
    assert state.state == "11"
    assert (
        state.attributes["Description"]
        == "Downtown Seattle to Downtown Bellevue via I-90"
    )
    assert state.attributes["TimeUpdated"] == datetime(
        2017, 1, 21, 15, 10, tzinfo=timezone(timedelta(hours=-8))
    )


async def test_travel_sensor_platform_setup(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
) -> None:
    """Test the wsdot Travel Time sensor still supports setup from platform config."""
    assert await async_setup_component(
        hass,
        Platform.SENSOR,
        {
            Platform.SENSOR: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_API_KEY: "foo",
                    CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I90 EB"}],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    state = hass.states.get("sensor.seattle_bellevue_via_i_90_eb_am")
    assert state is not None
    assert state.name == "Seattle-Bellevue via I-90 (EB AM)"
    assert (
        state.attributes["Description"]
        == "Downtown Seattle to Downtown Bellevue via I-90"
    )
    assert state.attributes["TimeUpdated"] == datetime(
        2017, 1, 21, 15, 10, tzinfo=timezone(timedelta(hours=-8))
    )


async def test_travel_sensor_platform_setup_bad_routes(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
) -> None:
    """Test the wsdot Travel Time sensor platform upgrade skips unknown route ids."""
    assert await async_setup_component(
        hass,
        Platform.SENSOR,
        {
            Platform.SENSOR: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_API_KEY: "foo",
                    CONF_TRAVEL_TIMES: [{CONF_ID: 4096, CONF_NAME: "Mars Expressway"}],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    entry = next(iter(hass.config_entries.async_entries(DOMAIN)), None)
    assert entry is not None
    assert entry.subentries == {}


@pytest.mark.parametrize(
    "api_key",
    [
        "foo",
        "bar",
    ],
    ids=["key-matches-", "key-does-not-match-"],
)
@pytest.mark.parametrize(
    "subentries",
    [
        [],
    ],
    ids=[""],
)
async def test_travel_sensor_platform_setup_skipped(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_config_data: dict[str, Any],
    init_integration: MockConfigEntry,
    api_key: str,
) -> None:
    """Test the wsdot Travel Time sensor platform upgrade is skipped when already exists."""
    assert await async_setup_component(
        hass,
        Platform.SENSOR,
        {
            Platform.SENSOR: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_API_KEY: api_key,
                    CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I90 EB"}],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    entry = next(iter(hass.config_entries.async_entries(DOMAIN)), None)
    assert entry is not None
    assert entry.data[CONF_API_KEY] == mock_config_data[CONF_API_KEY]
    assert entry.subentries == {}
