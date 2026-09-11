"""Tests for the LaMetric time platform."""

from datetime import time
from unittest.mock import MagicMock

from demetriek import LaMetricConnectionError, LaMetricError, ScreensaverMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TIME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_START_TIME = "time.frenck_s_lametric_screensaver_start_time"
ENTITY_END_TIME = "time.frenck_s_lametric_screensaver_end_time"

pytestmark = pytest.mark.freeze_time("2025-01-15 12:00:00+00:00")


@pytest.mark.parametrize("init_integration", [Platform.TIME], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the LaMetric screensaver time entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "expected_kwarg"),
    [
        (ENTITY_START_TIME, "screensaver_start_time"),
        (ENTITY_END_TIME, "screensaver_end_time"),
    ],
    ids=["start_time", "end_time"],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_value(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    entity_id: str,
    expected_kwarg: str,
) -> None:
    """Test setting the LaMetric screensaver times, which are sent in UTC."""
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: "16:00:39"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lametric.display.assert_called_once_with(
        screensaver_mode=ScreensaverMode.TIME_BASED,
        **{expected_kwarg: time(0, 0, 39)},
    )


@pytest.mark.parametrize("device_fixture", ["device_sa5"])
@pytest.mark.usefixtures("init_integration")
async def test_unknown_times(hass: HomeAssistant) -> None:
    """Test devices that have no screensaver times configured."""
    state = hass.states.get("time.spyfly_s_lametric_sky_screensaver_start_time")
    assert state
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("time.spyfly_s_lametric_sky_screensaver_end_time")
    assert state
    assert state.state == STATE_UNKNOWN


async def test_no_screensaver_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lametric: MagicMock,
) -> None:
    """Test devices that do not report a screensaver get no time entities."""
    mock_lametric.device.return_value.display.screensaver = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_START_TIME) is None
    assert hass.states.get(ENTITY_END_TIME) is None


@pytest.mark.parametrize(
    ("side_effect", "error_message", "expected_state"),
    [
        (
            LaMetricError,
            "Invalid response from the LaMetric device",
            "16:00:39",
        ),
        (
            LaMetricConnectionError,
            "Error communicating with the LaMetric device",
            STATE_UNAVAILABLE,
        ),
    ],
    ids=["error", "connection_error"],
)
@pytest.mark.usefixtures("init_integration")
async def test_time_errors(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    side_effect: type[Exception],
    error_message: str,
    expected_state: str,
) -> None:
    """Test error handling of the LaMetric times."""
    mock_lametric.display.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_START_TIME, ATTR_TIME: "20:00:00"},
            blocking=True,
        )

    state = hass.states.get(ENTITY_START_TIME)
    assert state
    assert state.state == expected_state
