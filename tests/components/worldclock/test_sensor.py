"""The test for the World clock sensor platform."""

from datetime import tzinfo

import pytest

from homeassistant.components.worldclock.const import (
    CONF_TIME_FORMAT,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_NAME, CONF_TIME_ZONE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
async def time_zone() -> tzinfo | None:
    """Fixture for time zone."""
    return await dt_util.async_get_time_zone("America/New_York")


async def test_time_imported_from_yaml(
    hass: HomeAssistant, time_zone: tzinfo | None, issue_registry: ir.IssueRegistry
) -> None:
    """Test the time at a different location."""
    config = {"sensor": {"platform": "worldclock", "time_zone": "America/New_York"}}

    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.worldclock_sensor")
    assert state is not None

    assert state.state == dt_util.now(time_zone=time_zone).strftime("%H:%M")

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue
    assert issue.issue_domain == DOMAIN


async def test_time_from_config_entry(
    hass: HomeAssistant, time_zone: tzinfo | None, loaded_entry: MockConfigEntry
) -> None:
    """Test the time at a different location."""

    state = hass.states.get("sensor.worldclock_sensor")
    assert state is not None

    assert state.state == dt_util.now(time_zone=time_zone).strftime("%H:%M")


@pytest.mark.parametrize(
    "get_config",
    [
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_TIME_ZONE: "America/New_York",
            CONF_TIME_FORMAT: "%a, %b %d, %Y %I:%M %p",
        }
    ],
)
async def test_time_format(
    hass: HomeAssistant, time_zone: tzinfo | None, loaded_entry: MockConfigEntry
) -> None:
    """Test time_format setting."""

    state = hass.states.get("sensor.worldclock_sensor")
    assert state is not None

    assert state.state == dt_util.now(time_zone=time_zone).strftime(
        "%a, %b %d, %Y %I:%M %p"
    )
