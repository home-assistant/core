"""The sensor tests for the IPMA platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ipma.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG, MockLocation


async def test_ipma_fire_risk_create_sensors(hass: HomeAssistant) -> None:
    """Test creation of fire risk sensors."""

    with patch("pyipma.location.Location.get", return_value=MockLocation()):
        entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.hometown_fire_risk")

    assert state.state == "3"


async def test_ipma_uv_index_create_sensors(hass: HomeAssistant) -> None:
    """Test creation of uv index sensors."""

    with patch("pyipma.location.Location.get", return_value=MockLocation()):
        entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.hometown_uv_index")

    assert state.state == "6"


@pytest.mark.parametrize(
    ("now", "expected_state", "expected_type"),
    [
        # Only the yellow warning is in effect
        ("2024-12-26 18:00:00+00:00", "yellow", "Agitação Marítima"),
        # Yellow and orange overlap, the most severe wins
        ("2024-12-27 06:00:00+00:00", "orange", "Vento"),
        # Red warning is in effect
        ("2024-12-29 03:00:00+00:00", "red", "Precipitação"),
        # Warning times are UTC, independent of the configured time zone
        ("2024-12-26 12:30:00+00:00", "yellow", "Agitação Marítima"),
    ],
)
async def test_ipma_warning_create_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    now: str,
    expected_state: str,
    expected_type: str,
) -> None:
    """Test the warning sensor reports the most severe warning in effect."""
    await hass.config.async_set_time_zone("Atlantic/Azores")
    freezer.move_to(now)

    with patch("pyipma.location.Location.get", return_value=MockLocation()):
        entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.hometown_weather_alert")

    assert state.state == expected_state
    assert state.attributes["awarenessTypeName"] == expected_type


@pytest.mark.parametrize(
    "now",
    [
        # Before any warning starts
        "2024-12-26 10:00:00+00:00",
        # Between the end of the yellow warning and the start of the red one
        "2024-12-28 12:00:00+00:00",
    ],
)
async def test_ipma_warning_none_in_effect(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, now: str
) -> None:
    """Test the warning sensor is green when no warning is in effect."""
    await hass.config.async_set_time_zone("Atlantic/Azores")
    freezer.move_to(now)

    with patch("pyipma.location.Location.get", return_value=MockLocation()):
        entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.hometown_weather_alert")

    assert state.state == "green"
    assert "awarenessTypeName" not in state.attributes


async def test_ipma_warning_unavailable(hass: HomeAssistant) -> None:
    """Test the warning sensor is unknown when warnings cannot be retrieved."""

    with (
        patch("pyipma.location.Location.get", return_value=MockLocation()),
        patch.object(MockLocation, "warnings", AsyncMock(return_value=None)),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.hometown_weather_alert")

    assert state.state == STATE_UNKNOWN
